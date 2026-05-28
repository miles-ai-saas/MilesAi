"use client";

/**
 * 通用枚举 meta 拉取（见 lib/enum-meta.ts 链路说明）。
 * 各模块 `use-*-meta.ts` 仅绑定对应 `api.get*Meta`。
 */

import { useEffect, useState } from "react";

export function useEnumMeta<T>(fetcher: () => Promise<T>, enabled = true): T | null {
  const [meta, setMeta] = useState<T | null>(null);

  useEffect(() => {
    if (!enabled) return;
    void fetcher().then(setMeta).catch(() => setMeta(null));
    // fetcher 为模块级稳定引用（如 api.getFlowMeta），无需列入 deps
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  return meta;
}
