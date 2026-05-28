"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Props = {
  attachmentId: string;
  alt?: string;
};

/** 对话/工具生成图片预览：鉴权 ``GET /attachments/{id}/content``，非 OSS 签名 URL。 */
export function ChatArtifactImage({ attachmentId, alt }: Props) {
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
    return <div className="flex h-24 w-24 items-center justify-center rounded-lg bg-surface-muted text-xs text-ink-faint">加载中…</div>;
  }

  return <img src={src} alt={alt ?? "生成图片"} className="max-h-48 max-w-full rounded-lg object-contain ring-1 ring-line" />;
}
