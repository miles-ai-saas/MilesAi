"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ChatArtifactImage } from "@/components/agent/ChatArtifactImage";

type Props = {
  kind: string;
  attachmentId: string;
  mimeType?: string | null;
  caption?: string | null;
};

/** 对话生成物预览：图片 / 视频（鉴权 content API，非签名 URL）。 */
export function ChatArtifactMedia({ kind, attachmentId, mimeType, caption }: Props) {
  if (kind === "image") {
    return <ChatArtifactImage attachmentId={attachmentId} alt={caption ?? "生成图片"} />;
  }
  if (kind === "video") {
    return <ChatArtifactVideo attachmentId={attachmentId} mimeType={mimeType} caption={caption} />;
  }
  return null;
}

function ChatArtifactVideo({
  attachmentId,
  mimeType,
  caption,
}: {
  attachmentId: string;
  mimeType?: string | null;
  caption?: string | null;
}) {
  const [src, setSrc] = useState<string | null>(null);

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

  if (!src) {
    return (
      <div className="flex h-32 w-56 items-center justify-center rounded-lg bg-surface-muted text-xs text-ink-faint">
        视频加载中…
      </div>
    );
  }

  return (
    <video
      src={src}
      controls
      playsInline
      className="max-h-64 max-w-full rounded-lg ring-1 ring-line"
      aria-label={caption ?? "生成视频"}
    >
      <track kind="captions" />
      您的浏览器不支持视频播放（{mimeType ?? "video/mp4"}）
    </video>
  );
}
