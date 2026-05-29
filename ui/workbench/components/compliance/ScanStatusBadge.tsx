"use client";

export function ScanStatusBadge({ blocked, warned, scanningEnabled }: { blocked: boolean; warned: boolean; scanningEnabled: boolean }) {
  if (!scanningEnabled) {
    return (
      <span className="inline-flex items-center rounded-full bg-surface-muted px-2.5 py-0.5 text-xs font-medium text-ink-muted ring-1 ring-line">
        扫描未启用
      </span>
    );
  }
  if (blocked) {
    return <span className="inline-flex items-center rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700 ring-1 ring-red-200">将拦截</span>;
  }
  if (warned) {
    return (
      <span className="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-800 ring-1 ring-amber-200">警告</span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-800 ring-1 ring-emerald-200">通过</span>
  );
}
