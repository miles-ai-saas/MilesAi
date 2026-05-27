"use client";

/**
 * 标准分页列表状态（链路 §3，见 `lib/chains.ts`）。
 * 页面在 `useRequireAuth().ready` 为 true 时传 `enabled: true`；筛选项变化用 `resetKey` 回到第 1 页。
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { getApiErrorMessage } from "@/lib/api-error";
import type { PageResult } from "@/lib/types";
import { DEFAULT_PAGE_SIZE, normalizePageResult } from "@/lib/pagination";

export function usePagedList<T>(
  fetcher: (page: number, size: number) => Promise<PageResult<T>>,
  options?: { enabled?: boolean; resetKey?: string | number; pageSize?: number }
) {
  const enabled = options?.enabled ?? true;
  const pageSize = options?.pageSize ?? DEFAULT_PAGE_SIZE;
  const resetKey = options?.resetKey ?? "";

  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const [page, setPage] = useState(1);
  const [items, setItems] = useState<T[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPage(1);
  }, [resetKey]);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const raw = await fetcherRef.current(page, pageSize);
        const res = normalizePageResult<T>(raw);
        if (!cancelled) {
          setItems(res.items);
          setTotal(res.total);
        }
      } catch (e) {
        if (!cancelled) {
          setError(getApiErrorMessage(e, "加载失败"));
          setItems([]);
          setTotal(0);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [page, pageSize, enabled, resetKey]);

  const reload = useCallback(async () => {
    setError(null);
    try {
      const res = normalizePageResult<T>(await fetcherRef.current(page, pageSize));
      setItems(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(getApiErrorMessage(e, "加载失败"));
      throw e;
    }
  }, [page, pageSize]);

  const clearError = useCallback(() => setError(null), []);

  return {
    items,
    total,
    page,
    size: pageSize,
    loading,
    error,
    clearError,
    setPage,
    reload,
  };
}
