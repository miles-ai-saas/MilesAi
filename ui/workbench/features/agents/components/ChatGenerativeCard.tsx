"use client";

import Link from "next/link";
import { useState } from "react";
import { ChatArtifactMedia } from "@/features/agents/components/ChatArtifactMedia";
import { effectiveArtifactStatus } from "@/lib/generative-jobs";
import { api } from "@/lib/api";
import type { GenerativeJobOut } from "@/lib/types";

export type ChatGenerativeCardArtifact = {
  kind: string;
  attachment_id?: string | null;
  mime_type?: string | null;
  caption?: string | null;
  status?: string | null;
  job_id?: string | null;
  media_asset_id?: string | null;
  progress_percent?: number | null;
  progress_message?: string | null;
  error_message?: string | null;
};

type Props = {
  artifact: ChatGenerativeCardArtifact;
  onCancel?: (jobId: string) => void;
  onRetried?: (job: GenerativeJobOut) => void;
};

const PREVIEW_CLASS =
  "max-h-80 max-w-full h-full w-full cursor-pointer rounded-md object-contain ring-1 ring-line transition-opacity hover:opacity-85";

export function ChatGenerativeCard({ artifact, onCancel, onRetried }: Props) {
  const status = effectiveArtifactStatus(artifact);
  const [retryBusy, setRetryBusy] = useState(false);
  const [retryErr, setRetryErr] = useState<string | null>(null);

  const mediaHref = artifact.media_asset_id
    ? `/workbench/media-assets?id=${encodeURIComponent(artifact.media_asset_id)}`
    : "/workbench/media-assets";

  const onRetry = async () => {
    if (!artifact.job_id || retryBusy) return;
    setRetryBusy(true);
    setRetryErr(null);
    try {
      const job = await api.retryGenerativeJob(artifact.job_id);
      onRetried?.(job);
    } catch (e) {
      setRetryErr(e instanceof Error ? e.message : "重试失败");
    } finally {
      setRetryBusy(false);
    }
  };

  if (status === "pending" || status === "running") {
    const label = artifact.progress_message || (artifact.kind === "image" ? "图片生成中…" : "视频生成中…");
    const pct = artifact.progress_percent;
    return (
      <div className="w-full max-w-md overflow-hidden rounded-xl border border-amber-200/80 bg-amber-50/50">
        <div className="flex aspect-[4/3] flex-col items-center justify-center gap-2 bg-surface-muted px-4">
          <p className="text-sm text-ink-muted">{label}</p>
          {pct != null ? <p className="text-xs text-ink-faint">{pct}%</p> : null}
        </div>
        {pct != null ? (
          <div className="h-1.5 bg-amber-200/60">
            <div className="h-full bg-amber-600 transition-all duration-300" style={{ width: `${pct}%` }} />
          </div>
        ) : null}
        <div className="flex items-center justify-between gap-2 px-3 py-2">
          <span className="text-xs text-amber-900">{status === "pending" ? "排队中" : "生成中"}</span>
          {artifact.job_id && onCancel ? (
            <button type="button" className="btn-sm-ghost text-xs text-amber-900" onClick={() => onCancel(artifact.job_id!)}>
              取消
            </button>
          ) : null}
        </div>
      </div>
    );
  }

  if (status === "failed") {
    return (
      <div className="w-full max-w-md rounded-xl border border-red-200 bg-red-50/80 p-4">
        <p className="text-sm text-red-800">{artifact.error_message || artifact.caption || "生成失败"}</p>
        {retryErr ? <p className="mt-1 text-xs text-red-600">{retryErr}</p> : null}
        {artifact.job_id ? (
          <button type="button" className="btn-sm-primary mt-3 text-xs" disabled={retryBusy} onClick={() => void onRetry()}>
            {retryBusy ? "重试中…" : "重试"}
          </button>
        ) : null}
      </div>
    );
  }

  if (status === "cancelled") {
    return (
      <div className="w-full max-w-md rounded-xl border border-line bg-surface-muted px-4 py-6 text-center text-sm text-ink-faint">
        已取消
      </div>
    );
  }

  return (
    <div className="w-full max-w-md overflow-hidden rounded-xl border border-line bg-surface">
      {artifact.attachment_id ? (
        <div className="flex aspect-[4/3] items-center justify-center bg-surface-muted p-2">
          <ChatArtifactMedia
            kind={artifact.kind}
            attachmentId={artifact.attachment_id}
            mimeType={artifact.mime_type}
            caption={artifact.caption}
            className={PREVIEW_CLASS}
          />
        </div>
      ) : (
        <div className="px-4 py-6 text-sm text-ink-muted">{artifact.caption || "生成完成"}</div>
      )}
      <div className="px-3 py-2">
        <Link href={mediaHref} className="text-xs text-brand hover:underline">
          在生成素材中查看
        </Link>
      </div>
    </div>
  );
}
