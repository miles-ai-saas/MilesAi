"use client";

/**
 * 拉取 GET /prompt-templates/meta 枚举元数据；enabled=false 时不请求（弹窗未打开等）。
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
