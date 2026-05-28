"use client";

/**
 * 通用枚举 meta 拉取（见 lib/enum-meta.ts 链路说明）。
 * AppShell 内 MetaCacheProvider 按 cacheKey 去重；无 Provider 时退化为组件内单次请求。
 */

import { useContext, useEffect, useState, useSyncExternalStore } from "react";
import {
  MetaCacheContext,
  getCacheState,
  loadIntoCache,
  subscribeStore,
} from "@/lib/enum-meta-cache";

export function useEnumMeta<T>(cacheKey: string, fetcher: () => Promise<T>, enabled = true): T | null {
  const store = useContext(MetaCacheContext);

  const [fallback, setFallback] = useState<T | null>(null);
  useEffect(() => {
    if (store || !enabled) return;
    void fetcher().then(setFallback).catch(() => setFallback(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [store, cacheKey, enabled]);

  const cachedState = useSyncExternalStore(
    (onChange) => (store ? subscribeStore(store, cacheKey, onChange) : () => {}),
    () =>
      store
        ? getCacheState(store, cacheKey)
        : { data: fallback, loading: false, settled: fallback !== null },
    () => ({ data: null, loading: false, settled: false }),
  );

  useEffect(() => {
    if (!store || !enabled) return;
    loadIntoCache(store, cacheKey, fetcher);
  }, [store, cacheKey, enabled, fetcher]);

  if (!store) {
    return fallback;
  }
  return cachedState.data as T | null;
}
