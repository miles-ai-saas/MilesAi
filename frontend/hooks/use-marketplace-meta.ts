"use client";

/**
 * `GET /marketplace/meta` — 枚举字典（tenant/marketplace/meta.py → api → marketplace-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { MarketplaceMeta } from "@/lib/types";

export function useMarketplaceMeta(enabled = true) {
  const [meta, setMeta] = useState<MarketplaceMeta | null>(null);

  useEffect(() => {
    if (!enabled) return;
    void api.getMarketplaceMeta().then(setMeta).catch(() => setMeta(null));
  }, [enabled]);

  return meta;
}
