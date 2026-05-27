"use client";

/**
 * `GET /prompt-templates/meta` — 枚举字典（tenant/prompts/meta.py → api → prompt-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { PromptMeta } from "@/lib/types";

export function usePromptMeta(enabled = true) {
  const [meta, setMeta] = useState<PromptMeta | null>(null);

  useEffect(() => {
    if (!enabled) return;
    void api.getPromptMeta().then(setMeta).catch(() => setMeta(null));
  }, [enabled]);

  return meta;
}
