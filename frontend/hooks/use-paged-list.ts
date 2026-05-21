"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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

  useEffect(() => {
    setPage(1);
  }, [resetKey]);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const raw = await fetcherRef.current(page, pageSize);
        const res = normalizePageResult<T>(raw);
        if (!cancelled) {
          setItems(res.items);
          setTotal(res.total);
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
    const res = normalizePageResult<T>(await fetcherRef.current(page, pageSize));
    setItems(res.items);
    setTotal(res.total);
  }, [page, pageSize]);

  return {
    items,
    total,
    page,
    size: pageSize,
    loading,
    setPage,
    reload,
  };
}
