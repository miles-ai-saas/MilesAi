"use client";

import { totalPages } from "@/lib/pagination";

export interface PaginationProps {
  page: number;
  size: number;
  total: number;
  onPageChange: (page: number) => void;
  className?: string;
}

export function Pagination({ page, size, total, onPageChange, className = "" }: PaginationProps) {
  const safeTotal = Math.max(0, Number(total) || 0);
  const safeSize = Math.max(1, Number(size) || 1);
  const safePage = Math.max(1, Number(page) || 1);

  if (safeTotal === 0) {
    return null;
  }

  const pages = totalPages(safeTotal, safeSize);
  const from = (safePage - 1) * safeSize + 1;
  const to = Math.min(safePage * safeSize, safeTotal);

  return (
    <div
      className={`flex flex-wrap items-center justify-between gap-2 text-xs text-ink-muted ${className}`}
    >
      <span>
        {from}–{to} / {safeTotal}
      </span>
      <div className="flex gap-1">
        <button
          type="button"
          disabled={safePage <= 1}
          onClick={() => onPageChange(safePage - 1)}
          className="rounded-md border border-line bg-surface px-2 py-1 disabled:cursor-not-allowed disabled:opacity-40 hover:bg-brand-light hover:text-brand"
        >
          上一页
        </button>
        <button
          type="button"
          disabled={safePage >= pages}
          onClick={() => onPageChange(safePage + 1)}
          className="rounded-md border border-line bg-surface px-2 py-1 disabled:cursor-not-allowed disabled:opacity-40 hover:bg-brand-light hover:text-brand"
        >
          下一页
        </button>
      </div>
    </div>
  );
}
