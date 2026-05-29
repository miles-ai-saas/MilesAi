"use client";

import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import type { SystemAuditPageVm } from "@/features/system-audit/hooks/use-system-audit-page";
import { buildAuditLogSummary, resolveAuditOperatorLabel } from "@/features/system-audit/lib/audit-log-present";
import { formatAuditTime, shortenId } from "@/features/system-audit/lib/system-audit-shared";
import { auditActionLabel, auditResourceTypeLabel } from "@/lib/audit-labels";
import type { TenantAuditLog } from "@/lib/types";

export function SystemAuditTable({ vm }: { vm: SystemAuditPageVm }) {
  const { auditMeta, list, hasActiveFilters } = vm;

  if (list.loading) {
    return <p className="text-sm text-ink-muted">加载中…</p>;
  }

  return (
    <>
      <div className="card overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="border-b border-line bg-surface-muted text-xs text-ink-muted">
            <tr>
              <th className="whitespace-nowrap px-4 py-2">时间</th>
              <th className="whitespace-nowrap px-4 py-2">操作者</th>
              <th className="whitespace-nowrap px-4 py-2">动作</th>
              <th className="whitespace-nowrap px-4 py-2">资源</th>
              <th className="whitespace-nowrap px-4 py-2">IP</th>
              <th className="px-4 py-2">说明</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line-soft">
            {list.items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-ink-faint">
                  {hasActiveFilters ? "当前筛选条件下暂无审计记录" : "暂无审计记录"}
                </td>
              </tr>
            ) : (
              list.items.map((log: TenantAuditLog) => {
                const operator = resolveAuditOperatorLabel(log);
                const summary = buildAuditLogSummary(log);
                return (
                  <tr key={log.id}>
                    <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-ink-muted">{formatAuditTime(log.created_at)}</td>
                    <td className="px-4 py-3 text-ink" title={operator.title}>
                      {operator.label}
                    </td>
                    <td className="px-4 py-3 text-ink">{auditActionLabel(log.action, auditMeta)}</td>
                    <td className="px-4 py-3 text-ink-muted">
                      {log.resource_type ? (
                        <span title={log.resource_id ?? undefined}>
                          {auditResourceTypeLabel(log.resource_type, auditMeta)}
                          {log.resource_id ? ` · ${shortenId(log.resource_id)}` : ""}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-ink-muted">{log.ip_address ?? "—"}</td>
                    <td className="px-4 py-3 text-ink-muted">{summary || "—"}</td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      <ResourceListFooter className="mt-3" page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
    </>
  );
}
