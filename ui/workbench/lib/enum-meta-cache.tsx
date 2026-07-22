"use client";

/**
 * 枚举 meta 进程内缓存：同一会话、同一 cacheKey 只请求一次各域 meta 接口。
 * 由 AppShell 挂载 MetaCacheProvider；useEnumMeta 自动使用。
 */

import { createContext, useRef, type ReactNode } from "react";

export type CacheState = {
  data: unknown;
  loading: boolean;
  settled: boolean;
};

export type MetaCacheStore = {
  states: Map<string, CacheState>;
  inflight: Map<string, Promise<unknown>>;
  listeners: Map<string, Set<() => void>>;
};

export function createMetaCacheStore(): MetaCacheStore {
  return { states: new Map(), inflight: new Map(), listeners: new Map() };
}

/** 稳定的空状态引用，避免 useSyncExternalStore 因 Object.is 不匹配导致无限循环 */
const EMPTY_CACHE_STATE: CacheState = Object.freeze({ data: null, loading: false, settled: false });

export function getCacheState(store: MetaCacheStore, key: string): CacheState {
  return store.states.get(key) ?? EMPTY_CACHE_STATE;
}

export function notifyCache(store: MetaCacheStore, key: string) {
  store.listeners.get(key)?.forEach((listener) => listener());
}

export function subscribeStore(store: MetaCacheStore, key: string, listener: () => void) {
  if (!store.listeners.has(key)) {
    store.listeners.set(key, new Set());
  }
  store.listeners.get(key)!.add(listener);
  return () => store.listeners.get(key)?.delete(listener);
}

export function loadIntoCache(store: MetaCacheStore, key: string, fetcher: () => Promise<unknown>) {
  const prev = getCacheState(store, key);
  if (store.inflight.has(key) || (prev.settled && !prev.loading)) {
    return;
  }

  store.states.set(key, { data: prev.data, loading: true, settled: false });
  notifyCache(store, key);

  const promise = fetcher()
    .then((data) => {
      store.states.set(key, { data, loading: false, settled: true });
    })
    .catch(() => {
      store.states.set(key, { data: null, loading: false, settled: true });
    })
    .finally(() => {
      store.inflight.delete(key);
      notifyCache(store, key);
    });

  store.inflight.set(key, promise);
}

export const MetaCacheContext = createContext<MetaCacheStore | null>(null);

export function MetaCacheProvider({ children }: { children: ReactNode }) {
  const storeRef = useRef<MetaCacheStore | null>(null);
  if (!storeRef.current) {
    storeRef.current = createMetaCacheStore();
  }
  return <MetaCacheContext.Provider value={storeRef.current}>{children}</MetaCacheContext.Provider>;
}
