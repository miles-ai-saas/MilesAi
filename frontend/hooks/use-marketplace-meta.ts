"use client";

/**
 * 拉取 GET /marketplace/meta 枚举元数据；enabled=false 时不请求（弹窗未打开等）。
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
