"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { PageResult } from "@/lib/types";
import { DEFAULT_PAGE_SIZE, normalizePageResult } from "@/lib/pagination";

export function useInfiniteList<T>(
  fetcher: (page: number, size: number) => Promise<PageResult<T>>,
  options?: { enabled?: boolean; resetKey?: string | number; pageSize?: number },
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
  const [loadingMore, setLoadingMore] = useState(false);

  const hasMore = items.length < total;

  const loadPage = useCallback(
    async (targetPage: number, mode: "replace" | "append") => {
      const raw = await fetcherRef.current(targetPage, pageSize);
      const res = normalizePageResult<T>(raw);
      setTotal(res.total);
      setPage(targetPage);
      setItems((prev) => (mode === "append" ? [...prev, ...res.items] : res.items));
      return res;
    },
    [pageSize],
  );

  useEffect(() => {
    setPage(1);
    setItems([]);
    setTotal(0);
  }, [resetKey]);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        await loadPage(1, "replace");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [enabled, resetKey, loadPage]);

  const loadMore = useCallback(async () => {
    if (!enabled || loading || loadingMore || !hasMore) return;
    setLoadingMore(true);
    try {
      await loadPage(page + 1, "append");
    } finally {
      setLoadingMore(false);
    }
  }, [enabled, loading, loadingMore, hasMore, page, loadPage]);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      await loadPage(1, "replace");
    } finally {
      setLoading(false);
    }
  }, [loadPage]);

  return {
    items,
    total,
    page,
    size: pageSize,
    loading,
    loadingMore,
    hasMore,
    loadMore,
    reload,
  };
}
