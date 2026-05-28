"use client";

/**
 * `GET /skill-packages/meta` — 枚举字典（tenant/skills/meta.py → api → skill-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { api } from "@/lib/api";
import { useEnumMeta } from "@/hooks/use-enum-meta";
import type { SkillMeta } from "@/lib/types";

export function useSkillMeta(enabled = true) {
  return useEnumMeta<SkillMeta>("skills", api.getSkillMeta, enabled);
}
