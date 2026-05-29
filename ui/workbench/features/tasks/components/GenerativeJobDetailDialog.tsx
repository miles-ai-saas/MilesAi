"use client";

/** 生成任务详情：进度 SSE、取消、完成后预览。 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ChatArtifactMedia } from "@/components/agent/ChatArtifactMedia";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { api } from "@/lib/api";
import { subscribeGenerativeJobStream } from "@/lib/generative-job-stream";
import {
  canCancelGenerativeJob,
  canRetryGenerativeJob,
  generativeJobKindLabel,
  generativeJobSourceLabel,
  generativeJobStatusBadgeClass,
  generativeJobStatusLabel,
  isGenerativeJobTerminal,
} from "@/lib/generative-job-labels";
import type { GenerativeJobsMeta } from "@/lib/generative-job-labels";
import type { GenerativeJobOut } from "@/lib/types";

type Props = {
  open: boolean;
  jobId: string | null;
  jobMeta?: GenerativeJobsMeta | null;
  onClose: () => void;
  onChanged?: () => void;
};

function DetailField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-ink-faint">{label}</dt>
      <dd className="mt-0.5 text-sm text-ink">{children}</dd>
    </div>
  );
}

export function GenerativeJobDetailDialog({ open, jobId, jobMeta, onClose, onChanged }: Props) {
  const [job, setJob] = useState<GenerativeJobOut | null>(null);
  const [msg, setMsg] = useState("");
  const [acting, setActing] = useState(false);
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const applyJob = useCallback((row: GenerativeJobOut) => {
    setJob(row);
    setMsg("");
  }, []);

  const reload = useCallback(async () => {
    if (!jobId) return;
    setLoading(true);
    try {
      applyJob(await api.getGenerativeJob(jobId));
    } catch (e) {
      setJob(null);
      setMsg(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [jobId, applyJob]);

  useEffect(() => {
    if (!open || !jobId) {
      setJob(null);
      setMsg("");
      abortRef.current?.abort();
      abortRef.current = null;
      return;
    }
    void reload();
  }, [open, jobId, reload]);

  const [sseFailed, setSseFailed] = useState(false);

  useEffect(() => {
    if (!open || !jobId) {
      setSseFailed(false);
      return;
    }
    setSseFailed(false);
  }, [open, jobId]);

  useEffect(() => {
    if (!open || !jobId || !job || isGenerativeJobTerminal(job.status)) {
      abortRef.current?.abort();
      abortRef.current = null;
      return;
    }
    const ac = new AbortController();
    abortRef.current = ac;
    void subscribeGenerativeJobStream(
      jobId,
      (row) => {
        applyJob(row);
        if (isGenerativeJobTerminal(row.status)) {
          onChanged?.();
        }
      },
      ac.signal,
    ).catch(() => setSseFailed(true));
    return () => ac.abort();
  }, [open, jobId, job?.status, applyJob, onChanged]);

  const onCancel = async () => {
    if (!jobId) return;
    setActing(true);
    try {
      applyJob(await api.cancelGenerativeJob(jobId));
      onChanged?.();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "取消失败");
    } finally {
      setActing(false);
    }
  };

  const onRetry = async () => {
    if (!jobId) return;
    setActing(true);
    try {
      applyJob(await api.retryGenerativeJob(jobId));
      setSseFailed(false);
      onChanged?.();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "重试失败");
    } finally {
      setActing(false);
    }
  };

  const celeryTaskHref = job?.celery_task_record_id ? `/workbench/tasks?category=celery&task=${encodeURIComponent(job.celery_task_record_id)}` : null;

  const prompt = job?.params && typeof job.params.prompt === "string" ? job.params.prompt : "";

  return (
    <ResourceDialog
      open={open}
      onClose={onClose}
      title="生成任务详情"
      description={jobId ? `ID · ${jobId}` : undefined}
      footer={
        job ? (
          <div className="flex flex-wrap items-center justify-end gap-2">
            <button type="button" className="btn-ghost text-sm" disabled={loading || acting} onClick={() => void reload()}>
              {loading ? "刷新中…" : "刷新"}
            </button>
            {canRetryGenerativeJob(job.status) && (
              <button type="button" className="btn-primary text-sm" disabled={acting} onClick={() => void onRetry()}>
                重试
              </button>
            )}
            {canCancelGenerativeJob(job.status) && (
              <button type="button" className="btn-secondary text-sm text-red-600" disabled={acting} onClick={() => void onCancel()}>
                取消任务
              </button>
            )}
          </div>
        ) : null
      }
    >
      {msg ? <p className="mb-3 text-sm text-red-600">{msg}</p> : null}
      {loading && !job ? (
        <p className="text-sm text-ink-muted">加载中…</p>
      ) : !job ? (
        <p className="text-sm text-ink-muted">暂无数据</p>
      ) : (
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
          {job.status === "success" &&
          (job.result?.attachment_id || (Array.isArray(job.result?.attachment_ids) && (job.result.attachment_ids as string[]).length > 0)) ? (
            <div className="col-span-full">
              <DetailField label="生成物">
                <div className="flex flex-wrap gap-3">
                  {(Array.isArray(job.result?.attachment_ids) && (job.result.attachment_ids as string[]).length > 0
                    ? (job.result.attachment_ids as string[])
                    : [String(job.result!.attachment_id)]
                  ).map((attId) => (
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
      )}
    </ResourceDialog>
  );
}
