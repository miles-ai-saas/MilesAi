"use client";

import type { ReactNode } from "react";

/** 模型页圆角筛选芯片（与列表页 FilterChip 样式不同） */
export function ModelFilterChip({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        active
          ? "rounded-full border border-brand bg-brand-light/50 px-3 py-1 text-xs font-medium text-brand"
          : "rounded-full border border-border bg-surface px-3 py-1 text-xs text-ink-muted hover:border-brand/30"
      }
    >
      {children}
    </button>
  );
}
