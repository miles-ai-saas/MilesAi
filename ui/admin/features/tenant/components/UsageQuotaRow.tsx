"use client";

export function UsageQuotaRow({
  label,
  used,
  max,
  unit = "",
  onMaxChange,
}: {
  label: string;
  used: number;
  max: number;
  unit?: string;
  onMaxChange: (value: number) => void;
}) {
  const pct = max > 0 ? Math.min(100, Math.round((used / max) * 100)) : 0;
  const warn = pct >= 90;
  const over = max > 0 && used > max;

  return (
    <div className={`rounded-lg border p-4 ${over ? "border-amber-300 bg-amber-50/40" : "border-line-soft bg-surface"}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <span className="font-medium text-ink">{label}</span>
            <span className={`cell-numeric text-xs ${warn || over ? "font-medium text-amber-700" : "cell-muted"}`}>
              {used.toLocaleString()}
              {unit} / {max.toLocaleString()}
              {unit}
              {max > 0 && ` (${pct}%)`}
            </span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-line-soft">
            <div
              className={`h-full rounded-full transition-all ${over ? "bg-red-500" : warn ? "bg-amber-500" : "bg-brand"}`}
              style={{ width: `${max > 0 ? pct : 0}%` }}
            />
          </div>
        </div>
        <label className="shrink-0 sm:w-32">
          <span className="text-xs cell-muted">配额上限</span>
          <input type="number" min={0} className="input-field mt-1 w-full sm:w-32" value={max} onChange={(e) => onMaxChange(Number(e.target.value))} />
        </label>
      </div>
    </div>
  );
}
