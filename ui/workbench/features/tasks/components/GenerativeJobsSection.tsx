"use client";

/** 任务中心 — 生成任务（generative_jobs）列表区块。 */

import { GenerativeJobDetailDialog } from "@/features/tasks/components/GenerativeJobDetailDialog";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { StatChip } from "@/components/ui/StatChip";
import { useGenerativeJobsSection, type GenerativeJobsListApi } from "@/features/tasks/hooks/use-generative-jobs-section";
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

export type { GenerativeJobsListApi };

function GenerativeJobRow({
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

type Props = {
  enabled: boolean;
  search: string;
  filter: string;
  msg: string;
  onMsg: (msg: string) => void;
  onExposeList?: (api: GenerativeJobsListApi) => void;
};

export function GenerativeJobsSection({ enabled, search, filter, msg, onMsg, onExposeList }: Props) {
  const vm = useGenerativeJobsSection({ enabled, search, filter, onMsg, onExposeList });

  if (!enabled) return null;

  if (vm.list.loading && vm.list.items.length === 0) {
    return <p className="col-span-full py-16 text-center text-sm text-ink-muted">加载中…</p>;
  }

  return (
    <>
      <div className="col-span-full flex flex-wrap gap-2">
        {vm.kindFilterOptions.map((opt) => (
          <button
            key={opt.value || "all"}
            type="button"
            onClick={() => vm.setKindFilter(opt.value)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              vm.kindFilter === opt.value ? "bg-brand text-white" : "bg-surface text-ink-muted ring-1 ring-line hover:text-ink"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <div className="col-span-full grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <StatChip label="生成任务总数" value={String(vm.list.total)} hint="当前筛选" />
        <StatChip label="本页进行中" value={String(vm.pageStats.running + vm.pageStats.pending)} hint={`失败 ${vm.pageStats.failed}（当前页）`} />
        <StatChip label="本页展示" value={String(vm.filtered.length)} hint="受搜索影响" />
      </div>

      <div className="col-span-full space-y-3">
        {vm.selectedJobIds.size > 0 ? (
          <div className="flex items-center justify-between rounded-lg border border-line bg-surface-subtle/50 px-4 py-2">
            <span className="text-xs text-ink-muted">已选 {vm.selectedJobIds.size} 条</span>
            <button type="button" className="text-xs font-medium text-red-600 hover:underline" onClick={() => void vm.batchCancelSelected()}>
              批量取消
            </button>
          </div>
        ) : null}
        {!vm.list.loading && vm.filtered.length === 0 && (
          <p className="rounded-xl border border-dashed border-line py-12 text-center text-sm text-ink-faint">
            暂无生成任务。在智能体对话或流程中生图/生视频后会出现在此。
          </p>
        )}
        {vm.cancellableOnPage.length > 0 && vm.filtered.length > 0 ? (
          <p className="text-xs text-ink-faint">可勾选 {vm.cancellableOnPage.length} 条待取消任务</p>
        ) : null}
        {vm.filtered.map((j) => (
          <GenerativeJobRow
            key={j.id}
            job={j}
            jobMeta={vm.jobMeta}
            selected={vm.selectedJobIds.has(j.id)}
            onSelectChange={(checked) => vm.toggleJobSelection(j.id, checked)}
            onViewDetail={() => vm.openDetail(j.id)}
            onCancel={() => void vm.onCancel(j.id)}
            onRetry={() => void vm.onRetry(j.id)}
          />
        ))}
      </div>

      {!vm.list.loading ? (
        <div className="col-span-full">
          <ResourceListFooter
            page={vm.list.page}
            size={vm.list.size}
            total={vm.list.total}
            onPageChange={vm.list.setPage}
            onSizeChange={vm.list.setSize}
          />
        </div>
      ) : null}

      <GenerativeJobDetailDialog
        open={!!vm.detailJobId}
        jobId={vm.detailJobId}
        jobMeta={vm.jobMeta}
        onClose={vm.closeDetail}
        onChanged={() => void vm.list.reload()}
      />
    </>
  );
}
