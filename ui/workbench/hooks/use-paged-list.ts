"use client";

import { usePagedList as usePagedListShared } from "@milesai/ui-shared/hooks/use-paged-list";
import { getApiErrorMessage } from "@/lib/api-error";
import type { PageResult } from "@/lib/types";

/**
 * 标准分页列表状态（链路 §3，见 `lib/chains.ts`）。
 * 页面在 `useRequireAuth().ready` 为 true 时传 `enabled: true`；筛选项变化用 `resetKey` 回到第 1 页。
 */
export function usePagedList<T>(
  fetcher: (page: number, size: number) => Promise<PageResult<T>>,
  options?: { enabled?: boolean; resetKey?: string | number; pageSize?: number },
) {
  return usePagedListShared(fetcher, {
    ...options,
    getErrorMessage: getApiErrorMessage,
  });
}
