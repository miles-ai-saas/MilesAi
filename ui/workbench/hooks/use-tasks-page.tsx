"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useGenerativeJobMeta } from "@/hooks/use-generative-job-meta";
import { useTaskMeta } from "@/hooks/use-task-meta";
import { canCancelTask } from "@/components/task/TaskDetailDialog";
import { filterBySearch } from "@/lib/filter-search";
import { generativeJobStatusFilterOptions } from "@/lib/generative-job-labels";
import { taskStatusFilterOptions } from "@/lib/task-labels";
import type { TaskCategory } from "@/lib/tasks-page-shared";

export function useTasksPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { ready } = useRequireAuth();
  const taskMeta = useTaskMeta(ready);
  const generativeMeta = useGenerativeJobMeta(ready);

  const categoryParam = searchParams.get("category");
  const category: TaskCategory = categoryParam === "generative" ? "generative" : "celery";

  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("");
  const [msg, setMsg] = useState("");
  const [detailTaskId, setDetailTaskId] = useState<string | null>(null);
  const [selectedTaskIds, setSelectedTaskIds] = useState<Set<string>>(new Set());
  const generativeListApi = useRef<{ reload: () => void } | null>(null);
  const [generativeListLoading, setGenerativeListLoading] = useState(false);

  const taskFromUrl = searchParams.get("task");

  useEffect(() => {
    if (taskFromUrl && category === "celery") setDetailTaskId(taskFromUrl);
  }, [taskFromUrl, category]);

  const setCategory = useCallback(
    (next: TaskCategory) => {
      setSearch("");
      setFilter("");
      setMsg("");
      setDetailTaskId(null);
      const params = new URLSearchParams();
      if (next === "generative") params.set("category", "generative");
      const q = params.toString();
      router.replace(q ? `/workbench/tasks?${q}` : "/workbench/tasks", { scroll: false });
    },
    [router],
  );

  const closeDetail = useCallback(() => {
    setDetailTaskId(null);
    const params = new URLSearchParams(searchParams.toString());
    params.delete("task");
    const q = params.toString();
    router.replace(q ? `/workbench/tasks?${q}` : "/workbench/tasks", { scroll: false });
  }, [router, searchParams]);

  const openDetail = useCallback(
    (id: string) => {
      setDetailTaskId(id);
      const params = new URLSearchParams(searchParams.toString());
      params.set("category", "celery");
      params.set("task", id);
      router.replace(`/workbench/tasks?${params.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

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

  return {
    ready,
    category,
    setCategory,
    search,
    setSearch,
    filter,
    msg,
    setMsg,
    taskMeta,
    list,
    filtered,
    pageStats,
    statusTabs,
    onFilterChange,
    selectedTaskIds,
    cancellableOnPage,
    toggleTaskSelection,
    batchCancelSelected,
    detailTaskId,
    openDetail,
    closeDetail,
    act,
    isGenerative,
    listRefreshing,
    refreshList,
    onGenerativeExposeList,
  };
}

export type TasksPageVm = ReturnType<typeof useTasksPage>;
