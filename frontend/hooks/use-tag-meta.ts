"use client";

/**
 * 拉取 GET /tags/meta 枚举元数据；enabled=false 时不请求（弹窗未打开等）。
 */


import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { TagMeta } from "@/lib/types";

export function useTagMeta(enabled = true) {
  const [meta, setMeta] = useState<TagMeta | null>(null);

  useEffect(() => {
    if (!enabled) return;
    void api.getTagMeta().then(setMeta).catch(() => setMeta(null));
  }, [enabled]);

  return meta;
}
