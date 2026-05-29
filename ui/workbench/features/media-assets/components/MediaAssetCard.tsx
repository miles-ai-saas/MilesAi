"use client";

import { ChatArtifactMedia } from "@/components/agent/ChatArtifactMedia";
import { mediaAssetKindLabel, mediaAssetSourceLabel } from "@/lib/media-asset-labels";
import { formatMediaBytes } from "@/lib/media-assets-page-shared";
import type { KnowledgeBase, MediaAsset } from "@/lib/types";

export function MediaAssetCard({
  asset,
  kbs,
  onPromote,
  onDelete,
}: {
  asset: MediaAsset;
  kbs: KnowledgeBase[];
  onPromote: () => void;
  onDelete: () => void;
}) {
  return (
    <article className="flex flex-col rounded-lg border border-line bg-surface p-3 shadow-sm">
      <div className="mb-2 flex min-h-[120px] items-center justify-center rounded-md bg-surface-muted">
        <ChatArtifactMedia
          kind={asset.kind}
          attachmentId={asset.attachment_id}
          mimeType={asset.attachment?.mime_type}
          caption={asset.title ?? undefined}
          posterAttachmentId={asset.kind === "video" ? (asset.cover_attachment_id ?? asset.cover_attachment?.id) : undefined}
        />
      </div>
      <p className="truncate text-sm font-medium text-ink">{asset.title ?? asset.attachment?.filename ?? "未命名"}</p>
      <p className="mt-1 text-xs text-ink-muted">
        {mediaAssetKindLabel(asset.kind)} · {mediaAssetSourceLabel(asset.source)}
        {asset.attachment?.file_size != null ? ` · ${formatMediaBytes(asset.attachment.file_size)}` : ""}
      </p>
      {asset.prompt && (
        <p className="mt-2 line-clamp-2 text-xs text-ink-faint" title={asset.prompt}>
          {asset.prompt}
        </p>
      )}
      <p className="mt-1 text-[10px] text-ink-faint">
        {new Date(asset.created_at).toLocaleString()}
        {asset.kb_document_id ? " · 已入库" : ""}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {!asset.kb_document_id && (asset.kind === "image" || asset.kind === "video") && kbs.length > 0 && (
          <button type="button" className="btn-sm-primary text-xs" onClick={onPromote}>
            加入知识库
          </button>
        )}
        <button type="button" className="btn-sm-ghost text-xs text-red-600" onClick={onDelete}>
          删除
        </button>
      </div>
    </article>
  );
}
