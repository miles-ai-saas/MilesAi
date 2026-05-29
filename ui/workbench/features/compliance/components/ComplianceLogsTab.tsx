"use client";

import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import type { CompliancePageVm } from "@/features/compliance/hooks/use-compliance-page";
import { COMPLIANCE_MAIN_TABS, COMPLIANCE_PAGE_DESC } from "@/features/compliance/lib/compliance-page-shared";
import type { InterceptLog } from "@/lib/types";

export function ComplianceLogsTab({ vm }: { vm: CompliancePageVm }) {
  const { logs, search, setSearch, tab, setTab, filteredLogs, actionLabel } = vm;

  return (
    <ResourceListLayout
      title="合规与安全"
      description={COMPLIANCE_PAGE_DESC}
      searchPlaceholder="搜索模块、命中词或内容摘要"
      search={search}
      onSearchChange={setSearch}
      tabs={COMPLIANCE_MAIN_TABS}
      activeTab={tab}
      onTabChange={(k) => setTab(k as typeof tab)}
      loading={logs.loading}
      footer={
        !logs.loading ? (
          <ResourceListFooter page={logs.page} size={logs.size} total={logs.total} onPageChange={logs.setPage} onSizeChange={logs.setSize} />
        ) : null
      }
    >
      <div className="col-span-full space-y-3">
        {!logs.loading && filteredLogs.length === 0 && (
          <p className="rounded-xl border border-dashed border-line py-12 text-center text-sm text-ink-faint">暂无拦截记录</p>
        )}
        {filteredLogs.map((l: InterceptLog) => (
          <article key={l.id} className="rounded-xl border border-line bg-surface p-4 shadow-card transition hover:border-brand/20">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <span className="font-medium text-ink">{l.module}</span>
                <span className="badge bg-brand-light text-brand">{l.direction === "in" ? "输入" : "输出"}</span>
                <span className={`badge ${l.action === "block" ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-800"}`}>{actionLabel(l.action)}</span>
                {l.matched_word && <span className="text-sm text-brand">命中「{l.matched_word}」</span>}
              </div>
              <time className="shrink-0 font-mono text-xs text-ink-faint">{new Date(l.created_at).toLocaleString("zh-CN")}</time>
            </div>
            {l.content_snippet && (
              <p className="mt-3 rounded-lg bg-surface-muted px-3 py-2 text-sm leading-relaxed text-ink-muted line-clamp-3">{l.content_snippet}</p>
            )}
          </article>
        ))}
      </div>
    </ResourceListLayout>
  );
}
