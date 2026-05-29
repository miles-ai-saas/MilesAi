"use client";

import Link from "next/link";
import { TaskStatusBadge } from "@/features/tasks/components/TaskStatusBadge";
import { canCancelTask, canRetryTask } from "@/features/tasks/components/TaskDetailDialog";
import type { TaskMeta, TaskRecord } from "@/lib/types";

export function TaskRow({
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
