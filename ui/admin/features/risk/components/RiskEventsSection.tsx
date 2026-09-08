"use client";

import { ListFooter } from "@/components/list/ListFooter";
import type { RiskPageVm } from "@/features/risk/hooks/use-risk-page";

export function RiskEventsSection({ vm }: { vm: RiskPageVm }) {
  const { events, onResolveEvent } = vm;

  return (
    <section className="card p-4">
      <h2 className="text-sm font-semibold text-ink">风险事件</h2>
      {events.loading ? (
        <p className="mt-3 text-sm text-ink-muted">加载中…</p>
      ) : (
        <>
          <ul className="admin-data-list mt-3">
            {events.items.length === 0 && <li className="text-ink-faint">暂无风险事件</li>}
            {events.items.map((e) => (
              <li key={e.id} className="admin-data-row flex items-center justify-between gap-2">
                <span>
                  <span className="cell-primary">{e.event_type}</span>
                  <span className="cell-muted"> · {e.severity}</span>
                  {e.ip_address && <span className="admin-data-meta"> · {e.ip_address}</span>}
                  <span className="admin-data-meta ml-2">{e.created_at.slice(0, 19)}</span>
                </span>
                {!e.is_resolved ? (
                  <button type="button" className="text-xs text-brand hover:underline" onClick={() => void onResolveEvent(e.id)}>
                    标记已处理
                  </button>
                ) : (
                  <span className="text-xs text-emerald-600">已处理</span>
                )}
              </li>
            ))}
          </ul>
          <ListFooter className="mt-3" page={events.page} size={events.size} total={events.total} onPageChange={events.setPage} onSizeChange={events.setSize} />
        </>
      )}
    </section>
  );
}
