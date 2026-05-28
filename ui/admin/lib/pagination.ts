import type { PageResult } from "@/lib/types";

/** 列表默认每页条数，与后端 get_page_params 默认一致 */
export const DEFAULT_PAGE_SIZE = 10;

/** 分页条数可选值（不超过后端 size 上限 100） */
export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100] as const;

export function buildPageQuery(page: number, size: number = DEFAULT_PAGE_SIZE): string {
  return `page=${page}&size=${size}`;
}

export function totalPages(total: number, size: number): number {
  const safeSize = Math.max(1, size);
  return Math.max(1, Math.ceil(total / safeSize));
}

/** 总条数超过每页大小时才需要分页 */
export function needsPagination(total: number, size: number = DEFAULT_PAGE_SIZE): boolean {
  const safeTotal = Math.max(0, Number(total) || 0);
  const safeSize = Math.max(1, Number(size) || DEFAULT_PAGE_SIZE);
  return safeTotal > safeSize;
}

/** 统一解析后端分页结构 */
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

  if (total === 0 && items.length > 0) {
    total = items.length;
  }

  return { items, total, page, size };
}
