"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { SystemAuditTable } from "@/features/system-audit/components/SystemAuditTable";
import type { SystemAuditPageVm } from "@/features/system-audit/hooks/use-system-audit-page";
import { SYSTEM_AUDIT_PAGE_DESC } from "@/features/system-audit/lib/system-audit-shared";

export function SystemAuditPageView({ vm }: { vm: SystemAuditPageVm }) {
  const {
    actionFilter,
    setActionFilter,
    resourceFilter,
    setResourceFilter,
    list,
    actionOptions,
    resourceOptions,
    hasActiveFilters,
    clearFilters,
  } = vm;

  return (
    <div className="w-full">
      <PageHeader
        title="审计日志"
        description={SYSTEM_AUDIT_PAGE_DESC}
        action={
          <button type="button" className="btn-sm-outline" disabled={list.loading} onClick={() => void list.reload()}>
            {list.loading ? "刷新中…" : "刷新"}
          </button>
        }
      />

      {list.error ? (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <span>{list.error}</span>
          <button type="button" className="btn-sm-outline text-red-700" onClick={() => void list.reload()}>
            重试
          </button>
        </div>
      ) : null}

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select className="input-field w-auto text-sm" value={resourceFilter} onChange={(e) => setResourceFilter(e.target.value)} aria-label="资源类型">
          {resourceOptions.map((o) => (
            <option key={o.value || "all"} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <select className="input-field w-auto text-sm" value={actionFilter} onChange={(e) => setActionFilter(e.target.value)} aria-label="动作">
          {actionOptions.map((o) => (
            <option key={o.value || "all"} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        {hasActiveFilters ? (
          <button type="button" className="btn-sm-ghost text-sm" onClick={clearFilters}>
            清除筛选
          </button>
        ) : null}
        {!list.loading ? <span className="text-xs text-ink-faint">共 {list.total} 条</span> : null}
      </div>

      <SystemAuditTable vm={vm} />
    </div>
  );
}
