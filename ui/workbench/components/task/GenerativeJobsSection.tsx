"use client";

/** 任务中心 — 生成任务（generative_jobs）列表区块。 */

import { GenerativeJobDetailDialog } from "@/components/task/GenerativeJobDetailDialog";
import { GenerativeJobRow } from "@/components/task/GenerativeJobRow";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { StatChip } from "@/components/ui/StatChip";
import { useGenerativeJobsSection, type GenerativeJobsListApi } from "@/hooks/use-generative-jobs-section";

export type { GenerativeJobsListApi };

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
