"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useGenerativeJobMeta } from "@/features/tasks/hooks/use-generative-job-meta";
import { useTaskMeta } from "@/features/tasks/hooks/use-task-meta";
import { canCancelTask } from "@/features/tasks/components/TaskDetailDialog";
import { filterBySearch } from "@/lib/filter-search";
import { generativeJobStatusFilterOptions } from "@/lib/generative-job-labels";
import { taskStatusFilterOptions } from "@/features/tasks/lib/task-labels";
import type { TaskCategory } from "@/features/tasks/lib/tasks-page-shared";

export function useTasksCeleryList(category: TaskCategory) {
  const { ready } = useRequireAuth();
  const taskMeta = useTaskMeta(ready);
  const generativeMeta = useGenerativeJobMeta(ready);

  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("");
  const [msg, setMsg] = useState("");
  const [selectedTaskIds, setSelectedTaskIds] = useState<Set<string>>(new Set());
  const generativeListApi = useRef<{ reload: () => void } | null>(null);
  const [generativeListLoading, setGenerativeListLoading] = useState(false);

  const list = usePagedList(useCallback((p, s) => api.listTasks(p, s, filter || undefined), [filter]), {
    enabled: ready && category === "celery",
    resetKey: `${filter}-${category}`,
  });

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (t) => `${t.task_name} ${t.celery_task_id} ${t.resource_type ?? ""} ${t.fail_reason ?? ""}`),
    [list.items, search],
  );

  const pageStats = useMemo(() => {
    let running = 0;
    let pending = 0;
    let failed = 0;
    for (const t of list.items) {
      if (t.status === "running") running += 1;
      else if (t.status === "pending") pending += 1;
      else if (t.status === "failed") failed += 1;
    }
    return { running, pending, failed };
  }, [list.items]);

  const onFilterChange = (key: string) => {
    setFilter(key);
    setSearch("");
    setSelectedTaskIds(new Set());
  };

  const cancellableOnPage = useMemo(() => filtered.filter((t) => canCancelTask(t)), [filtered]);

  const toggleTaskSelection = (taskId: string, checked: boolean) => {
    setSelectedTaskIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(taskId);
      else next.delete(taskId);
      return next;
    });
  };

  const batchCancelSelected = async () => {
    if (selectedTaskIds.size === 0) return;
    setMsg("");
    try {
      const res = await api.batchCancelTasks([...selectedTaskIds]);
      setMsg(`已取消 ${res.cancelled.length} 条${res.skipped.length ? `，跳过 ${res.skipped.length} 条` : ""}`);
      setSelectedTaskIds(new Set());
      await list.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "批量取消失败");
    }
  };

  const statusTabs = useMemo(() => {
    const opts = category === "generative" ? generativeJobStatusFilterOptions(generativeMeta) : taskStatusFilterOptions(taskMeta);
    return opts.map((o) => ({ key: o.value, label: o.label }));
  }, [category, taskMeta, generativeMeta]);

  const act = async (id: string, action: "cancel" | "retry") => {
    setMsg("");
    try {
      if (action === "cancel") await api.cancelTask(id);
      else await api.retryTask(id);
      setMsg(action === "cancel" ? "已取消" : "已重新提交");
      await list.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "操作失败");
    }
  };

  const isGenerative = category === "generative";
  const listRefreshing = isGenerative ? generativeListLoading : list.loading;

  const refreshList = () => {
    if (isGenerative) void generativeListApi.current?.reload();
    else void list.reload();
  };

  const onGenerativeExposeList = (api: { reload: () => void; loading: boolean }) => {
    generativeListApi.current = { reload: api.reload };
    setGenerativeListLoading(api.loading);
  };

  const resetOnCategoryChange = () => {
    setSearch("");
    setFilter("");
    setMsg("");
    setSelectedTaskIds(new Set());
  };

  return {
    ready,
    taskMeta,
    search,
    setSearch,
    filter,
    msg,
    setMsg,
    list,
    filtered,
    pageStats,
    statusTabs,
    onFilterChange,
    selectedTaskIds,
    cancellableOnPage,
    toggleTaskSelection,
    batchCancelSelected,
    act,
    isGenerative,
    listRefreshing,
    refreshList,
    onGenerativeExposeList,
    resetOnCategoryChange,
  };
}

export type TasksCelerySlice = ReturnType<typeof useTasksCeleryList>;
