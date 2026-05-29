"use client";

import { Pagination } from "./pagination";

export type ListFooterProps = {
  page: number;
  size: number;
  total: number;
  onPageChange: (page: number) => void;
  onSizeChange?: (size: number) => void;
  className?: string;
  noMoreText?: string;
  /** 无数据时的容器 class，默认紧凑间距 */
  emptyClassName?: string;
};

export function ListFooter({
  page,
  size,
  total,
  onPageChange,
  onSizeChange,
  className = "",
  noMoreText = "没有更多数据了",
  emptyClassName = "py-6 text-center text-sm text-ink-faint",
}: ListFooterProps) {
  const safeTotal = Math.max(0, Number(total) || 0);

  if (safeTotal > 0) {
    return (
      <div className={`mt-3 border-t border-line-soft pt-3 ${className}`.trim()}>
        <Pagination page={page} size={size} total={safeTotal} onPageChange={onPageChange} onSizeChange={onSizeChange} />
      </div>
    );
  }

  return <p className={`${emptyClassName} ${className}`.trim()}>{noMoreText}</p>;
}
