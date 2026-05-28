/**
 * 分页契约（链路 §3）：`buildPageQuery` 拼 query → `getPage` → `normalizePageResult`。
 * 见 `lib/chains.ts` §3。
 */

import type { PageResult } from "@/lib/types";

export { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS, totalPages } from "@milesai/ui-shared/lib/pagination";
import { DEFAULT_PAGE_SIZE } from "@milesai/ui-shared/lib/pagination";

export function buildPageQuery(page: number, size: number = DEFAULT_PAGE_SIZE): string {
  return `page=${page}&size=${size}`;
}

/** 总条数超过每页大小时才需要分页 */
export function needsPagination(total: number, size: number = DEFAULT_PAGE_SIZE): boolean {
  const safeTotal = Math.max(0, Number(total) || 0);
  const safeSize = Math.max(1, Number(size) || DEFAULT_PAGE_SIZE);
  return safeTotal > safeSize;
}

/** 统一解析后端分页结构，避免 total 缺失导致 0–0 / 0 */
export function normalizePageResult<T>(raw: unknown): PageResult<T> {
  if (Array.isArray(raw)) {
    const items = raw as T[];
    return {
      items,
      total: items.length,
      page: 1,
      size: items.length || DEFAULT_PAGE_SIZE,
    };
  }

  const body = (raw ?? {}) as Record<string, unknown>;
  const nested = (body.pagination ?? body.meta ?? body.page_info) as Record<string, unknown> | undefined;

  const items = (body.items ?? body.list ?? body.records ?? body.data ?? []) as T[];
  let total = Number(body.total ?? body.total_count ?? body.totalCount ?? body.count ?? nested?.total ?? nested?.total_count);
  let page = Number(body.page ?? body.page_num ?? nested?.page ?? 1);
  let size = Number(body.size ?? body.page_size ?? body.pageSize ?? nested?.size ?? DEFAULT_PAGE_SIZE);

  if (!Number.isFinite(total) || total < 0) total = 0;
  if (!Number.isFinite(page) || page < 1) page = 1;
  if (!Number.isFinite(size) || size < 1) size = DEFAULT_PAGE_SIZE;

  // 有数据但 total 为 0 时，按当前页条数兜底（常见于响应字段不一致）
  if (total === 0 && items.length > 0) {
    total = items.length;
  }

  return { items, total, page, size };
}
