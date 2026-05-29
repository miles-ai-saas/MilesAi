"use client";

/** 生成任务详情：进度 SSE、取消、完成后预览。 */

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { GenerativeJobDetailDialogBody } from "@/features/tasks/components/GenerativeJobDetailDialogBody";
import { useGenerativeJobDetailDialog } from "@/features/tasks/hooks/use-generative-job-detail-dialog";
import type { GenerativeJobsMeta } from "@/lib/generative-job-labels";

type Props = {
  open: boolean;
  jobId: string | null;
  jobMeta?: GenerativeJobsMeta | null;
  onClose: () => void;
  onChanged?: () => void;
};

export function GenerativeJobDetailDialog({ open, jobId, jobMeta, onClose, onChanged }: Props) {
  const vm = useGenerativeJobDetailDialog({ open, jobId, onChanged });

  return (
    <ResourceDialog
      open={open}
      onClose={onClose}
      title="生成任务详情"
      description={jobId ? `ID · ${jobId}` : undefined}
      footer={
        vm.job ? (
          <div className="flex flex-wrap items-center justify-end gap-2">
            <button type="button" className="btn-ghost text-sm" disabled={vm.loading || vm.acting} onClick={() => void vm.reload()}>
              {vm.loading ? "刷新中…" : "刷新"}
            </button>
            {vm.canRetry && (
              <button type="button" className="btn-primary text-sm" disabled={vm.acting} onClick={() => void vm.onRetry()}>
                重试
              </button>
            )}
            {vm.canCancel && (
              <button type="button" className="btn-secondary text-sm text-red-600" disabled={vm.acting} onClick={() => void vm.onCancel()}>
                取消任务
              </button>
            )}
          </div>
        ) : null
      }
    >
      {vm.msg ? <p className="mb-3 text-sm text-red-600">{vm.msg}</p> : null}
      <GenerativeJobDetailDialogBody vm={vm} jobMeta={jobMeta} />
    </ResourceDialog>
  );
}
