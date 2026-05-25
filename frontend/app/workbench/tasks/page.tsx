"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { filterBySearch } from "@/lib/filter-search";
import {
  TASK_STATUS_TABS,
  taskStatusBadgeClass,
  taskStatusLabel,
} from "@/lib/task-labels";
import type { TaskRecord } from "@/lib/types";

const PAGE_DESC =
  "查看文档入库等异步任务执行状态；支持按状态筛选、搜索、取消与重试（列表每 8 秒自动刷新）。";

function StatChip({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface px-4 py-3 shadow-card">
      <p className="text-xs text-ink-muted">{label}</p>
      <p className="mt-0.5 text-2xl font-bold tabular-nums text-brand">{value}</p>
      {hint ? <p className="mt-1 text-xs text-ink-faint">{hint}</p> : null}
    </div>
  );
}

function PageMessage({ message, onDismiss }: { message: string; onDismiss?: () => void }) {
  return (
    <div className="col-span-full flex items-start justify-between gap-3 rounded-xl border border-line bg-brand-light/40 px-4 py-3 text-sm text-ink">
      <p className="min-w-0 flex-1">{message}</p>
      {onDismiss && (
        <button type="button" className="shrink-0 text-xs text-ink-muted hover:text-ink" onClick={onDismiss}>
          关闭
        </button>
      )}
    </div>
  );
}

function TaskStatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${taskStatusBadgeClass(status)}`}
    >
      {taskStatusLabel(status)}
    </span>
  );
}

function canCancel(task: TaskRecord) {
  return ["pending", "running"].includes(task.status);
}

function canRetry(task: TaskRecord) {
  return (
    ["failed", "cancelled", "success"].includes(task.status) && task.resource_type === "document"
  );
}

function TaskRow({
  task,
  onCancel,
  onRetry,
}: {
  task: TaskRecord;
  onCancel: () => void;
  onRetry: () => void;
}) {
  return (
    <article className="rounded-xl border border-line bg-surface p-4 shadow-card transition hover:border-brand/20">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium text-ink">{task.task_name}</h3>
            <TaskStatusBadge status={task.status} />
          </div>
          <p className="mt-2 font-mono text-xs text-ink-faint">
            Celery · {task.celery_task_id.slice(0, 20)}
            {task.celery_task_id.length > 20 ? "…" : ""}
          </p>
          <p className="mt-1 text-xs text-ink-muted">
            {task.resource_type || "无关联资源"}
            {task.resource_id ? ` · ${String(task.resource_id).slice(0, 8)}…` : ""}
          </p>
          <time className="mt-2 block text-xs text-ink-faint">
            创建于 {new Date(task.created_at).toLocaleString("zh-CN")}
          </time>
          {task.fail_reason && (
            <p className="mt-3 rounded-lg bg-red-50/80 px-3 py-2 text-xs text-red-700 line-clamp-2">
              {task.fail_reason}
            </p>
          )}
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-3 sm:flex-col sm:items-end">
          <Link
            href={`/workbench/tasks/${task.id}`}
            className="btn-secondary px-3 py-1.5 text-xs"
          >
            查看详情
          </Link>
          {canCancel(task) && (
            <button type="button" className="text-xs text-red-600 hover:underline" onClick={onCancel}>
              取消任务
            </button>
          )}
          {canRetry(task) && (
            <button type="button" className="text-xs text-brand hover:underline" onClick={onRetry}>
              重试
            </button>
          )}
        </div>
      </div>
    </article>
  );
}

export default function TasksPage() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("");
  const [msg, setMsg] = useState("");

  const list = usePagedList(
    useCallback((p, s) => api.listTasks(p, s, filter || undefined), [filter]),
    { enabled: ready, resetKey: filter },
  );

  useEffect(() => {
    if (!ready) return;
    const t = setInterval(() => list.reload(), 8000);
    return () => clearInterval(t);
  }, [ready, list.reload, filter]);

  const filtered = useMemo(
    () =>
      filterBySearch(
        list.items,
        search,
        (t) =>
          `${t.task_name} ${t.celery_task_id} ${t.resource_type ?? ""} ${t.fail_reason ?? ""}`,
      ),
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
  };

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

  return (
    <ResourceListLayout
      title="任务"
      description={PAGE_DESC}
      searchPlaceholder="搜索任务名称、ID 或失败原因"
      search={search}
      onSearchChange={setSearch}
      tabs={[...TASK_STATUS_TABS]}
      activeTab={filter}
      onTabChange={onFilterChange}
      loading={list.loading}
      headerAction={
        <button
          type="button"
          className="btn-ghost shrink-0 text-sm"
          disabled={list.loading}
          onClick={() => void list.reload()}
        >
          {list.loading ? "刷新中…" : "刷新"}
        </button>
      }
      footer={
        !list.loading ? (
          <ResourceListFooter
            page={list.page}
            size={list.size}
            total={list.total}
            onPageChange={list.setPage}
          />
        ) : null
      }
    >
      {msg && <PageMessage message={msg} onDismiss={() => setMsg("")} />}

      <div className="col-span-full grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatChip label="任务总数" value={String(list.total)} hint="当前筛选条件下" />
        <StatChip
          label="本页运行中"
          value={String(pageStats.running)}
          hint={`等待 ${pageStats.pending} · 失败 ${pageStats.failed}（当前页）`}
        />
        <StatChip label="本页展示" value={String(filtered.length)} hint="受搜索筛选影响" />
        <StatChip
          label="自动刷新"
          value="8s"
          hint={filter ? `状态：${taskStatusLabel(filter)}` : "全部状态"}
        />
      </div>

      <div className="col-span-full space-y-3">
        {!list.loading && filtered.length === 0 && (
          <p className="rounded-xl border border-dashed border-line py-12 text-center text-sm text-ink-faint">
            暂无匹配的任务
          </p>
        )}
        {filtered.map((t) => (
          <TaskRow
            key={t.id}
            task={t}
            onCancel={() => void act(t.id, "cancel")}
            onRetry={() => void act(t.id, "retry")}
          />
        ))}
      </div>
    </ResourceListLayout>
  );
}
