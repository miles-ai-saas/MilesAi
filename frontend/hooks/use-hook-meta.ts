"use client";

/**
 * 拉取 GET /hooks/meta 枚举元数据；enabled=false 时不请求。
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { HookMeta } from "@/lib/types";

export function useHookMeta(enabled = true) {
  const [meta, setMeta] = useState<HookMeta | null>(null);

  useEffect(() => {
    if (!enabled) return;
    void api.getHookMeta().then(setMeta).catch(() => setMeta(null));
  }, [enabled]);

  return meta;
}
