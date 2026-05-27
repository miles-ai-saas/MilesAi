"use client";

import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS, totalPages } from "@/lib/pagination";

export interface PaginationProps {
  page: number;
  size: number;
  total: number;
  onPageChange: (page: number) => void;
  onSizeChange?: (size: number) => void;
  pageSizeOptions?: readonly number[];
  className?: string;
}

const navBtnClass =
  "px-2.5 py-1.5 text-ink transition hover:bg-brand-light hover:text-brand disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-ink";

export function Pagination({
  page,
  size,
  total,
  onPageChange,
  onSizeChange,
  pageSizeOptions = PAGE_SIZE_OPTIONS,
  className = "",
}: PaginationProps) {
  const safeTotal = Math.max(0, Number(total) || 0);
  const safeSize = Math.max(1, Number(size) || DEFAULT_PAGE_SIZE);
  const safePage = Math.max(1, Number(page) || 1);

  if (safeTotal === 0) {
    return null;
  }

  const pages = totalPages(safeTotal, safeSize);
  const options = pageSizeOptions.includes(safeSize)
    ? pageSizeOptions
    : [...pageSizeOptions, safeSize].sort((a, b) => a - b);

  return (
    <nav
      aria-label="列表分页"
      className={`flex flex-wrap items-center justify-end gap-x-3 gap-y-2 text-xs text-ink-muted ${className}`}
    >
      <span className="tabular-nums">共 {safeTotal.toLocaleString()} 条</span>

      {onSizeChange && (
        <>
          <span className="hidden h-3 w-px bg-line sm:block" aria-hidden />
          <label className="inline-flex items-center gap-1.5">
            <span>每页</span>
            <select
              className="rounded-md border border-line bg-surface px-2 py-1.5 text-xs text-ink outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/15"
              value={safeSize}
              onChange={(e) => onSizeChange(Number(e.target.value))}
              aria-label="每页条数"
            >
              {options.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
            <span>条</span>
          </label>
        </>
      )}

      <span className="hidden h-3 w-px bg-line sm:block" aria-hidden />

      <div className="inline-flex items-stretch overflow-hidden rounded-md border border-line bg-surface shadow-sm">
        <button
          type="button"
          disabled={safePage <= 1}
          onClick={() => onPageChange(safePage - 1)}
          className={navBtnClass}
          aria-label="上一页"
        >
          ‹
        </button>
        <span
          className="flex min-w-[3.25rem] items-center justify-center border-x border-line px-2 py-1.5 tabular-nums text-ink"
          aria-live="polite"
        >
          {safePage} / {pages}
        </span>
        <button
          type="button"
          disabled={safePage >= pages}
          onClick={() => onPageChange(safePage + 1)}
          className={navBtnClass}
          aria-label="下一页"
        >
          ›
        </button>
      </div>
    </nav>
  );
}
