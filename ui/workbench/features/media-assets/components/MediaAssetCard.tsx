"use client";

import { ChatArtifactMedia } from "@/features/agents";
import type { KnowledgeBase, MediaAsset } from "@/lib/types";

const MEDIA_KIND_LABELS: Record<string, string> = {
  image: "图片",
  video: "视频",
};

const MEDIA_SOURCE_LABELS: Record<string, string> = {
  agent_tool: "智能体生成",
  flow_node: "流程生成",
};

function mediaAssetKindLabel(kind: string): string {
  return MEDIA_KIND_LABELS[kind] ?? kind;
}

function mediaAssetSourceLabel(source: string): string {
  return MEDIA_SOURCE_LABELS[source] ?? source;
}

function formatMediaBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

const MEDIA_PREVIEW_CLASS =
  "max-h-full max-w-full h-full w-full cursor-pointer rounded-md object-contain ring-1 ring-line transition-opacity hover:opacity-85";

export function MediaAssetCard({
  asset,
  kbs,
  onPromote,
  onDelete,
  highlighted = false,
}: {
  asset: MediaAsset;
  kbs: KnowledgeBase[];
  onPromote: () => void;
  onDelete: () => void;
  highlighted?: boolean;
}) {
  return (
    <article
      id={`media-asset-${asset.id}`}
      className={`group flex min-w-0 flex-col overflow-hidden rounded-xl border bg-surface shadow-sm transition-shadow hover:shadow-md ${
        highlighted ? "border-brand ring-2 ring-brand/40" : "border-line"
      }`}
    >
      <div className="aspect-[4/3] w-full shrink-0 bg-surface-muted">
        <div className="flex h-full w-full items-center justify-center p-2">
          <ChatArtifactMedia
            kind={asset.kind}
            attachmentId={asset.attachment_id}
            mimeType={asset.attachment?.mime_type}
            caption={asset.title ?? undefined}
            posterAttachmentId={asset.kind === "video" ? (asset.cover_attachment_id ?? asset.cover_attachment?.id) : undefined}
            className={MEDIA_PREVIEW_CLASS}
          />
        </div>
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1 p-4">
        <p className="truncate text-sm font-medium text-ink" title={asset.title ?? asset.attachment?.filename ?? undefined}>
          {asset.title ?? asset.attachment?.filename ?? "未命名"}
        </p>
        <p className="truncate text-xs text-ink-muted">
          {mediaAssetKindLabel(asset.kind)} · {mediaAssetSourceLabel(asset.source)}
          {asset.attachment?.file_size != null ? ` · ${formatMediaBytes(asset.attachment.file_size)}` : ""}
        </p>
        {asset.prompt && (
          <p className="line-clamp-2 text-xs leading-relaxed text-ink-faint" title={asset.prompt}>
            {asset.prompt}
          </p>
        )}
        <p className="text-[11px] text-ink-faint">
          {new Date(asset.created_at).toLocaleString()}
          {asset.kb_document_id ? " · 已入库" : ""}
        </p>
        <div className="mt-auto flex flex-wrap items-center gap-2 pt-3">
          {!asset.kb_document_id && (asset.kind === "image" || asset.kind === "video") && kbs.length > 0 && (
            <button type="button" className="btn-sm-primary text-xs" onClick={onPromote}>
              加入知识库
            </button>
          )}
          <button type="button" className="btn-sm-ghost text-xs text-red-600" onClick={onDelete}>
            删除
          </button>
        </div>
      </div>
    </article>
  );
}
