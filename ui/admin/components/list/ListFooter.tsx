"use client";

import { Pagination } from "@/components/ui/Pagination";

type Props = {
  page: number;
  size: number;
  total: number;
  onPageChange: (page: number) => void;
  onSizeChange?: (size: number) => void;
  className?: string;
  noMoreText?: string;
};

export function ListFooter({
  page,
  size,
  total,
  onPageChange,
  onSizeChange,
  className = "",
  noMoreText = "没有更多数据了",
}: Props) {
  const safeTotal = Math.max(0, Number(total) || 0);

  if (safeTotal > 0) {
    return (
      <div className={`mt-3 border-t border-line-soft pt-3 ${className}`.trim()}>
        <Pagination
          page={page}
          size={size}
          total={safeTotal}
          onPageChange={onPageChange}
          onSizeChange={onSizeChange}
        />
      </div>
    );
  }

  return (
    <p className={`py-6 text-center text-sm text-ink-faint ${className}`}>{noMoreText}</p>
  );
}
