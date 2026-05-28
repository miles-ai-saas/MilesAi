/** 分页 UI 共享常量（与后端 get_page_params 默认一致） */

export const DEFAULT_PAGE_SIZE = 10;

export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100] as const;

export function totalPages(total: number, size: number): number {
  const safeSize = Math.max(1, size);
  return Math.max(1, Math.ceil(total / safeSize));
}
