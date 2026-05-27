"use client";

export function MarketplaceStarDisplay({ value, count }: { value: number; count?: number }) {
  const full = Math.round(value);
  return (
    <span className="inline-flex items-center gap-0.5 text-amber-500" title={`${value.toFixed(1)} 分`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className={i <= full ? "" : "opacity-25"}>
          ★
        </span>
      ))}
      {count !== undefined && <span className="ml-1 text-xs text-ink-faint">({count})</span>}
    </span>
  );
}
