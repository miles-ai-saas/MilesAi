"use client";

/**
 * 拉取 GET /attachments/meta 枚举元数据；enabled=false 时不请求（弹窗未打开等）。
 */


import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AttachmentMeta } from "@/lib/types";

export function useAttachmentMeta(enabled = true) {
  const [meta, setMeta] = useState<AttachmentMeta | null>(null);

  useEffect(() => {
    if (!enabled) return;
    void api.getAttachmentMeta().then(setMeta).catch(() => setMeta(null));
  }, [enabled]);

  return meta;
}
