"use client";

/** 任务中心：后台 Celery 任务 + 生成任务（generative_jobs）。 */

import Link from "next/link";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useGenerativeJobMeta } from "@/hooks/use-generative-job-meta";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { canCancelTask, canRetryTask, TaskDetailDialog } from "@/components/task/TaskDetailDialog";
import { GenerativeJobsSection } from "@/components/task/GenerativeJobsSection";
import { PageMessage } from "@/components/ui/PageMessage";
import { StatChip } from "@/components/ui/StatChip";
import { filterBySearch } from "@/lib/filter-search";
import { generativeJobStatusFilterOptions } from "@/lib/generative-job-labels";
import { taskStatusBadgeClass, taskStatusFilterOptions, taskStatusLabel } from "@/lib/task-labels";
import { useTaskMeta } from "@/hooks/use-task-meta";
import type { TaskRecord, TaskMeta } from "@/lib/types";

type TaskCategory = "celery" | "generative";

const CATEGORY_TABS: { key: TaskCategory; label: string }[] = [
  { key: "celery", label: "后台任务" },
  { key: "generative", label: "生成任务" },
];

const PAGE_DESC: Record<TaskCategory, string> = {
  celery: "文档入库等 Celery 异步任务；支持按状态筛选、搜索、取消与重试；点击「刷新」更新列表。",
  generative: "智能体对话、流程或 API 触发的生图/生视频任务；支持类型筛选、进度查看、取消与失败重试；可跳转关联的后台 Celery 记录；点击「刷新」更新列表。",
};

function TaskStatusBadge({ status, taskMeta }: { status: string; taskMeta: TaskMeta | null }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${taskStatusBadgeClass(status)}`}>
      {taskStatusLabel(status, taskMeta)}
    </span>
  );
}

function TaskRow({
  task,
  taskMeta,
  selected,
  onSelectChange,
  onViewDetail,
  onCancel,
  onRetry,
}: {
  task: TaskRecord;
  taskMeta: TaskMeta | null;
  selected?: boolean;
  onSelectChange?: (checked: boolean) => void;
  onViewDetail: () => void;
  onCancel: () => void;
  onRetry: () => void;
}) {
  const cancellable = canCancelTask(task);
  return (
    <article className="rounded-xl border border-line bg-surface p-4 shadow-card transition hover:border-brand/20">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 flex-1 gap-3">
          {onSelectChange && cancellable ? (
            <input
              type="checkbox"
              className="mt-1 h-4 w-4 shrink-0 rounded border-line text-brand"
              checked={selected ?? false}
              onChange={(e) => onSelectChange(e.target.checked)}
              aria-label={`选择任务 ${task.task_name}`}
            />
          ) : null}
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-medium text-ink">{task.task_name}</h3>
              <TaskStatusBadge status={task.status} taskMeta={taskMeta} />
            </div>
            <p className="mt-2 font-mono text-xs text-ink-faint">
              Celery · {task.celery_task_id.slice(0, 20)}
              {task.celery_task_id.length > 20 ? "…" : ""}
            </p>
            <p className="mt-1 text-xs text-ink-muted">
              {task.resource_type || "无关联资源"}
              {task.resource_id ? ` · ${String(task.resource_id).slice(0, 8)}…` : ""}
            </p>
            {task.resource_type === "generative_job" && task.resource_id ? (
              <Link
                href={`/workbench/tasks?category=generative&job=${encodeURIComponent(task.resource_id)}`}
                className="mt-1 inline-block text-xs text-brand hover:underline"
              >
                查看生成任务 →
              </Link>
            ) : null}
            <time className="mt-2 block text-xs text-ink-faint">创建于 {new Date(task.created_at).toLocaleString("zh-CN")}</time>
            {task.fail_reason && <p className="mt-3 rounded-lg bg-red-50/80 px-3 py-2 text-xs text-red-700 line-clamp-2">{task.fail_reason}</p>}
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-3 sm:flex-col sm:items-end">
          <button type="button" className="btn-secondary px-3 py-1.5 text-xs" onClick={onViewDetail}>
            查看详情
          </button>
          {canCancelTask(task) && (
            <button type="button" className="text-xs text-red-600 hover:underline" onClick={onCancel}>
              取消任务
            </button>
          )}
          {canRetryTask(task) && (
            <button type="button" className="text-xs text-brand hover:underline" onClick={onRetry}>
              重试
            </button>
          )}
        </div>
      </div>
    </article>
  );
}

function CategorySwitcher({ category, onChange }: { category: TaskCategory; onChange: (c: TaskCategory) => void }) {
  return (
    <div className="mb-4 flex gap-2">
      {CATEGORY_TABS.map((tab) => (
        <button
          key={tab.key}
          type="button"
          onClick={() => onChange(tab.key)}
          className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
            category === tab.key ? "bg-brand text-white shadow-sm" : "bg-surface text-ink-muted ring-1 ring-line hover:text-ink"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export default function TasksPage() {
  return (
    <Suspense fallback={<div className="py-12 text-center text-sm text-ink-muted">加载任务列表…</div>}>
      <TasksPageContent />
    </Suspense>
  );
}

function TasksPageContent() {
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

  const list = usePagedList(
    useCallback((p, s) => api.listTasks(p, s, filter || undefined), [filter]),
    { enabled: ready && category === "celery", resetKey: `${filter}-${category}` },
  );

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

  return (
    <ResourceListLayout
      title="任务中心"
      description={PAGE_DESC[category]}
      showSearch={false}
      search={search}
      onSearchChange={setSearch}
      tabs={statusTabs}
      activeTab={filter}
      onTabChange={onFilterChange}
      loading={!isGenerative && list.loading}
      headerAction={
        <div className="flex w-full flex-col gap-3 sm:flex-row sm:items-center sm:justify-end">
          <label className="relative block w-full sm:w-72">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint">
              <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
                <path
                  fillRule="evenodd"
                  d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z"
                  clipRule="evenodd"
                />
              </svg>
            </span>
            <input
              type="search"
              className="input w-full pl-9"
              placeholder={isGenerative ? "搜索 Prompt、ID 或错误信息" : "搜索任务名称、ID 或失败原因"}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
          <button type="button" className="btn-ghost shrink-0 text-sm" disabled={listRefreshing} onClick={refreshList}>
            {listRefreshing ? "刷新中…" : "刷新"}
          </button>
          {!isGenerative && selectedTaskIds.size > 0 ? (
            <button type="button" className="btn-sm-outline shrink-0 text-red-600" onClick={() => void batchCancelSelected()}>
              批量取消 ({selectedTaskIds.size})
            </button>
          ) : null}
        </div>
      }
      footer={
        !isGenerative && !list.loading ? (
          <ResourceListFooter page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
        ) : null
      }
    >
      <div className="col-span-full -mt-2 mb-2">
        <CategorySwitcher category={category} onChange={setCategory} />
      </div>

      {msg && <PageMessage message={msg} onDismiss={() => setMsg("")} />}

      {isGenerative ? (
        <GenerativeJobsSection
          enabled={ready}
          search={search}
          filter={filter}
          msg={msg}
          onMsg={setMsg}
          onExposeList={(api) => {
            generativeListApi.current = { reload: api.reload };
            setGenerativeListLoading(api.loading);
          }}
        />
      ) : (
        <>
          <div className="col-span-full grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <StatChip label="任务总数" value={String(list.total)} hint="当前筛选条件下" />
            <StatChip label="本页运行中" value={String(pageStats.running)} hint={`等待 ${pageStats.pending} · 失败 ${pageStats.failed}（当前页）`} />
            <StatChip label="本页展示" value={String(filtered.length)} hint="受搜索筛选影响" />
          </div>

          <div className="col-span-full space-y-3">
            {!list.loading && filtered.length === 0 && (
              <p className="rounded-xl border border-dashed border-line py-12 text-center text-sm text-ink-faint">暂无匹配的任务</p>
            )}
            {cancellableOnPage.length > 0 && filtered.length > 0 ? (
              <p className="text-xs text-ink-faint">可勾选 {cancellableOnPage.length} 条待取消任务，使用右上角「批量取消」</p>
            ) : null}
            {filtered.map((t) => (
              <TaskRow
                key={t.id}
                task={t}
                taskMeta={taskMeta}
                selected={selectedTaskIds.has(t.id)}
                onSelectChange={(checked) => toggleTaskSelection(t.id, checked)}
                onViewDetail={() => openDetail(t.id)}
                onCancel={() => void act(t.id, "cancel")}
                onRetry={() => void act(t.id, "retry")}
              />
            ))}
          </div>

          <TaskDetailDialog open={!!detailTaskId} taskId={detailTaskId} taskMeta={taskMeta} onClose={closeDetail} onChanged={() => void list.reload()} />
        </>
      )}
    </ResourceListLayout>
  );
}
