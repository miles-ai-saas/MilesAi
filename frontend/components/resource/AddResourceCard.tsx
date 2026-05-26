"use client";

/** 列表页「新增」占位卡（链路 §3）。 */

type Props = {
  label: string;
  hint: string;
  onClick: () => void;
};

export function AddResourceCard({ label, hint, onClick }: Props) {
  return (
    <button type="button" onClick={onClick} className="resource-add-card">
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-surface-muted text-2xl text-ink-faint">
        +
      </span>
      <span className="mt-3 text-sm font-medium text-ink">{label}</span>
      <span className="mt-1 text-xs text-ink-muted">{hint}</span>
    </button>
  );
}
