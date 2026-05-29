"use client";

import { usePagedList as usePagedListShared } from "@milesai/ui-shared/hooks/use-paged-list";
import { getApiErrorMessage } from "@/lib/api-error";
import type { PageResult } from "@/lib/types";

export function usePagedList<T>(
  fetcher: (page: number, size: number) => Promise<PageResult<T>>,
  options?: { enabled?: boolean; resetKey?: string | number; pageSize?: number },
) {
  return usePagedListShared(fetcher, {
    ...options,
    getErrorMessage: getApiErrorMessage,
  });
}
