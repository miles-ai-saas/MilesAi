"use client";

type BarItem = { label: string; value: number; color?: string };

type Props = {
  items: BarItem[];
  maxValue?: number;
  className?: string;
};

export function SimpleBarChart({ items, maxValue, className = "" }: Props) {
  const max = maxValue ?? Math.max(...items.map((i) => i.value), 1);

  return (
    <div className={`space-y-2 ${className}`}>
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-2 text-xs">
          <span className="w-20 shrink-0 text-ink-muted">{item.label}</span>
          <div className="h-5 min-w-0 flex-1 rounded bg-surface-muted">
            <div
              className="h-full rounded bg-brand transition-all"
              style={{
                width: `${Math.max(4, (item.value / max) * 100)}%`,
                backgroundColor: item.color,
              }}
            />
          </div>
          <span className="w-8 shrink-0 text-right font-medium text-ink">{item.value}</span>
        </div>
      ))}
    </div>
  );
}
