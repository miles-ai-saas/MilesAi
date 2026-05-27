"use client";

/**
 * `GET /kb/meta` — 枚举字典（tenant/kb/meta.py → api → kb-labels / document-status，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { KbMeta } from "@/lib/types";

export function useKbMeta(enabled = true) {
  const [meta, setMeta] = useState<KbMeta | null>(null);

  useEffect(() => {
    if (!enabled) return;
    void api.getKbMeta().then(setMeta).catch(() => setMeta(null));
  }, [enabled]);

  return meta;
}
