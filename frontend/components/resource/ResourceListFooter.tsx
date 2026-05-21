"use client";

import { Pagination } from "@/components/ui/Pagination";
import { needsPagination } from "@/lib/pagination";

type Props = {
  page: number;
  size: number;
  total: number;
  onPageChange: (page: number) => void;
  className?: string;
  noMoreText?: string;
};

/** 未达分页条件时展示「没有更多数据了」，达到时仅展示分页器（互斥） */
export function ResourceListFooter({
  page,
  size,
  total,
  onPageChange,
  className = "",
  noMoreText = "没有更多数据了",
}: Props) {
  const safeTotal = Math.max(0, Number(total) || 0);

  if (needsPagination(safeTotal, size)) {
    return (
      <Pagination
        page={page}
        size={size}
        total={safeTotal}
        onPageChange={onPageChange}
        className={className}
      />
    );
  }

  return (
    <p className={`py-12 text-center text-sm text-ink-faint ${className}`}>{noMoreText}</p>
  );
}
