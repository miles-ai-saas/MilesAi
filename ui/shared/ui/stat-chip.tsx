type Props = {
  label: string;
  value: string;
  hint?: string;
};

/** 列表页统计卡片（工具/监控/市场等共用） */
export function StatChip({ label, value, hint }: Props) {
  return (
    <div className="rounded-xl border border-line bg-surface px-4 py-3 shadow-card">
      <p className="text-xs text-ink-muted">{label}</p>
      <p className="mt-0.5 text-2xl font-bold tabular-nums text-brand">{value}</p>
      {hint ? <p className="mt-1 text-xs text-ink-faint line-clamp-2">{hint}</p> : null}
    </div>
  );
}
