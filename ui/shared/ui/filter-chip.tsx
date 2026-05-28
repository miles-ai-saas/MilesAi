"use client";

import type { ReactNode } from "react";

type Props = {
  active: boolean;
  onClick: () => void;
  label?: string;
  children?: ReactNode;
};

/** 筛选 Tab 芯片（支持 label 或 children） */
export function FilterChip({ active, onClick, label, children }: Props) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg px-3 py-1.5 text-xs transition ${
        active ? "bg-brand-light font-medium text-brand" : "text-ink-muted hover:bg-surface hover:text-ink"
      }`}
    >
      {children ?? label}
    </button>
  );
}
