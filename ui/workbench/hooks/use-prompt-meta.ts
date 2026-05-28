"use client";

/**
 * `GET /prompt-templates/meta` — 枚举字典（tenant/prompts/meta.py → api → prompt-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { api } from "@/lib/api";
import { useEnumMeta } from "@/hooks/use-enum-meta";
import type { PromptMeta } from "@/lib/types";

export function usePromptMeta(enabled = true) {
  return useEnumMeta<PromptMeta>("prompts", api.getPromptMeta, enabled);
}
