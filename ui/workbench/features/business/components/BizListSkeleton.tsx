/** 业务列表页通用骨架屏。 */

export function BizListPageSkeleton({ statCount = 3 }: { statCount?: number }) {
  return (
    <div className="space-y-4">
      <div className="space-y-3">
        <div className="h-8 w-48 animate-pulse rounded-lg bg-surface-muted" />
        <div className="h-4 w-72 animate-pulse rounded bg-surface-muted" />
      </div>
      <div
        className="grid gap-3 sm:grid-cols-2"
        style={{ gridTemplateColumns: `repeat(${Math.min(statCount, 5)}, minmax(0, 1fr))` }}
      >
        {Array.from({ length: statCount }, (_, i) => (
          <div key={i} className="h-20 animate-pulse rounded-xl bg-surface-muted" />
        ))}
      </div>
      <div className="h-[420px] animate-pulse rounded-xl bg-surface-muted" />
    </div>
  );
}

export function BizTableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="divide-y divide-line-soft">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex gap-4 px-4 py-4">
          <div className="h-4 w-1/3 animate-pulse rounded bg-surface-muted" />
          <div className="h-4 w-16 animate-pulse rounded bg-surface-muted" />
          <div className="hidden h-4 w-16 animate-pulse rounded bg-surface-muted sm:block" />
        </div>
      ))}
    </div>
  );
}
