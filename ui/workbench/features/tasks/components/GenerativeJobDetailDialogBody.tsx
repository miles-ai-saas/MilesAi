"use client";

import Link from "next/link";
import { ChatArtifactMedia } from "@/features/agents";
import type { GenerativeJobDetailDialogVm } from "@/features/tasks/hooks/use-generative-job-detail-dialog";
import {
  generativeJobKindLabel,
  generativeJobSourceLabel,
  generativeJobStatusBadgeClass,
  generativeJobStatusLabel,
  isGenerativeJobTerminal,
} from "@/lib/generative-job-labels";
import type { GenerativeJobsMeta } from "@/lib/generative-job-labels";

function DetailField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-ink-faint">{label}</dt>
      <dd className="mt-0.5 text-sm text-ink">{children}</dd>
    </div>
  );
}

function resultAttachmentIds(job: NonNullable<GenerativeJobDetailDialogVm["job"]>): string[] {
  if (Array.isArray(job.result?.attachment_ids) && (job.result.attachment_ids as string[]).length > 0) {
    return job.result.attachment_ids as string[];
  }
  if (job.result?.attachment_id) {
    return [String(job.result.attachment_id)];
  }
  return [];
}

type Props = {
  vm: GenerativeJobDetailDialogVm;
  jobMeta?: GenerativeJobsMeta | null;
};

export function GenerativeJobDetailDialogBody({ vm, jobMeta }: Props) {
  const { job, loading, sseFailed, celeryTaskHref, prompt } = vm;

  if (loading && !job) {
    return <p className="text-sm text-ink-muted">加载中…</p>;
  }
  if (!job) {
    return <p className="text-sm text-ink-muted">暂无数据</p>;
  }

  const attachments = resultAttachmentIds(job);

  return (
    <dl className="grid gap-3 sm:grid-cols-2">
      <DetailField label="状态">
        <span className={`inline-flex rounded-full px-2 py-0.5 text-xs ring-1 ${generativeJobStatusBadgeClass(job.status)}`}>
          {generativeJobStatusLabel(job.status, jobMeta)}
        </span>
      </DetailField>
      <DetailField label="类型">{generativeJobKindLabel(job.kind)}</DetailField>
      <DetailField label="来源">{generativeJobSourceLabel(job.source, jobMeta)}</DetailField>
      <DetailField label="进度">
        {job.progress_percent != null ? `${job.progress_percent}%` : "—"}
        {job.progress_message ? ` · ${job.progress_message}` : ""}
        {sseFailed && !isGenerativeJobTerminal(job.status) ? (
          <span className="mt-1 block text-xs text-amber-800">实时进度不可用，请点击「刷新」更新</span>
        ) : null}
      </DetailField>
      {job.progress_percent != null && !isGenerativeJobTerminal(job.status) ? (
        <div className="col-span-full">
          <div className="h-2 overflow-hidden rounded-full bg-surface-muted">
            <div className="h-full rounded-full bg-brand transition-all" style={{ width: `${job.progress_percent}%` }} />
          </div>
        </div>
      ) : null}
      <DetailField label="创建时间">{new Date(job.created_at).toLocaleString("zh-CN")}</DetailField>
      {job.celery_task_id ? (
        <DetailField label="Celery ID">
          <span className="font-mono text-xs">{job.celery_task_id}</span>
        </DetailField>
      ) : null}
      {celeryTaskHref ? (
        <div className="col-span-full">
          <Link href={celeryTaskHref} className="text-xs text-brand hover:underline">
            在后台任务中查看 Celery 记录 →
          </Link>
        </div>
      ) : null}
      {prompt ? (
        <div className="col-span-full">
          <DetailField label="Prompt">
            <p className="whitespace-pre-wrap text-sm">{prompt}</p>
          </DetailField>
        </div>
      ) : null}
      {job.error_message ? (
        <div className="col-span-full">
          <DetailField label="失败原因">
            <p className="text-sm text-red-700">{job.error_message}</p>
          </DetailField>
        </div>
      ) : null}
      {job.status === "success" && attachments.length > 0 ? (
        <div className="col-span-full">
          <DetailField label="生成物">
            <div className="flex flex-wrap gap-3">
              {attachments.map((attId) => (
                <ChatArtifactMedia
                  key={attId}
                  kind={(job.result!.kind as string) || "video"}
                  attachmentId={attId}
                  mimeType={(job.result!.mime_type as string) ?? null}
                />
              ))}
            </div>
          </DetailField>
          <Link href="/workbench/media-assets" className="mt-2 inline-block text-xs text-brand hover:underline">
            在生成素材中查看 →
          </Link>
        </div>
      ) : null}
    </dl>
  );
}
