"use client";

import {
  canCancelGenerativeJob,
  canRetryGenerativeJob,
  generativeJobKindLabel,
  generativeJobSourceLabel,
  generativeJobStatusBadgeClass,
  generativeJobStatusLabel,
} from "@/lib/generative-job-labels";
import type { GenerativeJobsMeta } from "@/lib/generative-job-labels";
import type { GenerativeJobOut } from "@/lib/types";

export function GenerativeJobRow({
  job,
  jobMeta,
  selected,
  onSelectChange,
  onViewDetail,
  onCancel,
  onRetry,
}: {
  job: GenerativeJobOut;
  jobMeta: GenerativeJobsMeta | null;
  selected?: boolean;
  onSelectChange?: (checked: boolean) => void;
  onViewDetail: () => void;
  onCancel: () => void;
  onRetry: () => void;
}) {
  const prompt = job.params && typeof job.params.prompt === "string" ? job.params.prompt : "";
  const cancellable = canCancelGenerativeJob(job.status);

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
              aria-label={`选择生成任务 ${job.id}`}
            />
          ) : null}
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-medium text-ink">{generativeJobKindLabel(job.kind)}</h3>
              <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${generativeJobStatusBadgeClass(job.status)}`}>
                {generativeJobStatusLabel(job.status, jobMeta)}
              </span>
              {job.progress_percent != null && (job.status === "pending" || job.status === "running") ? (
                <span className="text-xs text-ink-muted">{job.progress_percent}%</span>
              ) : null}
            </div>
            <p className="mt-1 text-xs text-ink-muted">
              {generativeJobSourceLabel(job.source, jobMeta)} · {job.id.slice(0, 8)}…
            </p>
            {prompt ? <p className="mt-2 line-clamp-2 text-sm text-ink-muted">{prompt}</p> : null}
            {job.progress_message && (job.status === "pending" || job.status === "running") ? (
              <p className="mt-1 text-xs text-amber-800">{job.progress_message}</p>
            ) : null}
            <time className="mt-2 block text-xs text-ink-faint">{new Date(job.created_at).toLocaleString("zh-CN")}</time>
            {job.error_message ? <p className="mt-2 rounded-lg bg-red-50/80 px-3 py-2 text-xs text-red-700 line-clamp-2">{job.error_message}</p> : null}
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap gap-3">
          <button type="button" className="btn-secondary px-3 py-1.5 text-xs" onClick={onViewDetail}>
            查看详情
          </button>
          {canCancelGenerativeJob(job.status) && (
            <button type="button" className="text-xs text-red-600 hover:underline" onClick={onCancel}>
              取消
            </button>
          )}
          {canRetryGenerativeJob(job.status) && (
            <button type="button" className="text-xs text-brand hover:underline" onClick={onRetry}>
              重试
            </button>
          )}
        </div>
      </div>
      {!canCancelGenerativeJob(job.status) && job.progress_percent != null && job.progress_percent > 0 && job.progress_percent < 100 ? (
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-surface-muted">
          <div className="h-full rounded-full bg-brand transition-all" style={{ width: `${job.progress_percent}%` }} />
        </div>
      ) : null}
    </article>
  );
}
