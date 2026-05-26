"use client";

/**
 * `GET /skill-packages/meta` — 枚举字典（tenant/skills/meta.py → api → skill-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
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
