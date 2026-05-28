"use client";

/**
 * `GET /marketplace/meta` — 枚举字典（tenant/marketplace/meta.py → api → marketplace-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { api } from "@/lib/api";
import { useEnumMeta } from "@/hooks/use-enum-meta";
import type { MarketplaceMeta } from "@/lib/types";

export function useMarketplaceMeta(enabled = true) {
  return useEnumMeta<MarketplaceMeta>(api.getMarketplaceMeta, enabled);
}
