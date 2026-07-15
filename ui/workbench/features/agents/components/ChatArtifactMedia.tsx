"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ImagePreviewDialog } from "@/features/agents/components/ImagePreviewDialog";

type Props = {
  kind: string;
  attachmentId: string;
  mimeType?: string | null;
  caption?: string | null;
  /** 视频列表缩略图（media_assets.cover_attachment_id） */
  posterAttachmentId?: string | null;
  /** 覆盖默认样式（如素材卡片传 max-h-80 获得更大预览） */
  className?: string;
};

/** 对话生成物预览：图片 / 视频（鉴权 content API，非签名 URL）。 */
export function ChatArtifactMedia({ kind, attachmentId, mimeType, caption, posterAttachmentId, className }: Props) {
  if (kind === "image") {
    return <ChatArtifactImage attachmentId={attachmentId} alt={caption ?? "生成图片"} className={className} />;
  }
  if (kind === "video") {
    return <ChatArtifactVideo attachmentId={attachmentId} mimeType={mimeType} caption={caption} posterAttachmentId={posterAttachmentId} className={className} />;
  }
  return null;
}

function ChatArtifactImage({ attachmentId, alt, className }: { attachmentId: string; alt?: string; className?: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);

  useEffect(() => {
    let url: string | null = null;
    let cancelled = false;
    void api.fetchAttachmentPreviewUrl(attachmentId).then((u) => {
      if (!cancelled) {
        url = u;
        setSrc(u);
      }
    });
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [attachmentId]);

  const openPreview = useCallback(() => {
    if (src) setPreviewOpen(true);
  }, [src]);

  if (!src) {
    return <div className="flex h-32 w-32 items-center justify-center rounded-lg bg-surface-muted text-xs text-ink-faint">加载中…</div>;
  }

  return (
    <>
      <img
        src={src}
        alt={alt ?? "生成图片"}
        className={className ?? "max-h-56 max-w-full cursor-pointer rounded-lg object-contain ring-1 ring-line transition-opacity hover:opacity-85"}
        onClick={openPreview}
        title="点击查看大图"
      />
      <ImagePreviewDialog open={previewOpen} src={src} alt={alt} onClose={() => setPreviewOpen(false)} />
    </>
  );
}

function ChatArtifactVideo({
  attachmentId,
  mimeType,
  caption,
  posterAttachmentId,
  className,
}: {
  attachmentId: string;
  mimeType?: string | null;
  caption?: string | null;
  posterAttachmentId?: string | null;
  className?: string;
}) {
  const [src, setSrc] = useState<string | null>(null);
  const [poster, setPoster] = useState<string | null>(null);

  useEffect(() => {
    let url: string | null = null;
    let cancelled = false;
    void api.fetchAttachmentPreviewUrl(attachmentId).then((u) => {
      if (!cancelled) {
        url = u;
        setSrc(u);
      }
    });
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [attachmentId]);

  useEffect(() => {
    if (!posterAttachmentId) {
      setPoster(null);
      return;
    }
    let url: string | null = null;
    let cancelled = false;
    void api.fetchAttachmentPreviewUrl(posterAttachmentId).then((u) => {
      if (!cancelled) {
        url = u;
        setPoster(u);
      }
    });
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [posterAttachmentId]);

  if (poster && !src) {
    return (
      <div className="relative flex h-full w-full max-w-full items-center justify-center">
        <img src={poster} alt={caption ?? "视频封面"} className={className ?? "max-h-56 max-w-full rounded-lg object-cover ring-1 ring-line"} />
        <span className="absolute bottom-2 right-2 rounded bg-black/50 px-1.5 py-0.5 text-[10px] text-white">点击播放加载视频</span>
      </div>
    );
  }

  if (!src) {
    return <div className="flex h-32 w-56 items-center justify-center rounded-lg bg-surface-muted text-xs text-ink-faint">视频加载中…</div>;
  }

  return (
    <video
      src={src}
      controls
      playsInline
      poster={poster ?? undefined}
      className={className ?? "max-h-64 max-w-full rounded-lg ring-1 ring-line"}
      aria-label={caption ?? "生成视频"}
    >
      <track kind="captions" />
      您的浏览器不支持视频播放（{mimeType ?? "video/mp4"}）
    </video>
  );
}
