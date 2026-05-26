"use client";

/**
 * 拉取 GET /skill-packages/meta 枚举元数据；enabled=false 时不请求（弹窗未打开等）。
 */


import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SkillMeta } from "@/lib/types";

export function useSkillMeta(enabled = true) {
  const [meta, setMeta] = useState<SkillMeta | null>(null);

  useEffect(() => {
    if (!enabled) return;
    void api.getSkillMeta().then(setMeta).catch(() => setMeta(null));
  }, [enabled]);

  return meta;
}
