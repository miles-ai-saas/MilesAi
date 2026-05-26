"use client";

/**
 * `GET /attachments/meta` — 枚举字典（tenant/attachments/meta.py → api → attachment-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
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
