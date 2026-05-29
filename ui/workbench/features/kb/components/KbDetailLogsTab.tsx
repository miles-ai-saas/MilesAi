"use client";

import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { searchSourceLabel } from "@/features/kb/lib/kb-labels";
import type { KbDetailPageVm } from "@/features/kb/hooks/use-kb-detail-page";

export function KbDetailLogsTab({ vm }: { vm: KbDetailPageVm }) {
  return (
    <section className="rounded-xl border border-line bg-surface p-5 shadow-card">
      <h2 className="text-sm font-semibold text-ink">检索记录</h2>
      <p className="mt-1 text-xs text-ink-faint">记录本库的 API 调试、智能体 RAG 与流程检索（仅本租户可见）</p>
      {vm.logs.loading ? (
        <p className="mt-4 text-sm text-ink-muted">加载中…</p>
      ) : vm.logs.items.length === 0 ? (
        <p className="mt-6 text-center text-sm text-ink-muted">暂无记录。在「检索测试」或绑定本库的智能体对话后会出现。</p>
      ) : (
        <>
          <ul className="mt-4 divide-y divide-line">
            {vm.logs.items.map((log) => (
              <li key={log.id} className="py-3 first:pt-0">
                <div className="flex flex-wrap items-center gap-2 text-xs text-ink-faint">
                  <time dateTime={log.created_at}>{new Date(log.created_at).toLocaleString()}</time>
                  <span className="rounded-md bg-surface-muted px-1.5 py-0.5">{log.retrieval_mode}</span>
                  <span>{searchSourceLabel(log.source, vm.kbMeta?.search_sources)}</span>
                  <span>
                    {log.hit_count} 命中 · {log.latency_ms} ms
                  </span>
                </div>
                <p className="mt-1.5 text-sm text-ink">{log.query}</p>
              </li>
            ))}
          </ul>
          <ResourceListFooter
            className="mt-4 border-t border-line pt-3"
            page={vm.logs.page}
            size={vm.logs.size}
            total={vm.logs.total}
            onPageChange={vm.logs.setPage}
            onSizeChange={vm.logs.setSize}
          />
        </>
      )}
    </section>
  );
}
