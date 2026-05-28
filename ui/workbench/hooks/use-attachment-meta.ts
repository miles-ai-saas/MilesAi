"use client";

/**
 * `GET /attachments/meta` — 枚举字典（tenant/attachments/meta.py → api → attachment-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { api } from "@/lib/api";
import { useEnumMeta } from "@/hooks/use-enum-meta";
import type { AttachmentMeta } from "@/lib/types";

export function useAttachmentMeta(enabled = true) {
  return useEnumMeta<AttachmentMeta>(api.getAttachmentMeta, enabled);
}
