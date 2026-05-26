"use client";

/**
 * 拉取 GET /kb/meta 枚举元数据；enabled=false 时不请求（弹窗未打开等）。
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
