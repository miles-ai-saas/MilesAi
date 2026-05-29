"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import type { SystemAuditPageVm } from "@/features/system-audit/hooks/use-system-audit-page";
import { auditActionLabel, auditResourceTypeLabel } from "@/lib/audit-labels";
import type { TenantAuditLog } from "@/lib/types";

const SYSTEM_AUDIT_PAGE_DESC = "记录租户内关键操作行为";

export function SystemAuditPageView({ vm }: { vm: SystemAuditPageVm }) {
  const { auditMeta, actionFilter, setActionFilter, resourceFilter, setResourceFilter, list, actionOptions, resourceOptions } = vm;

  return (
    <div className="w-full">
      <PageHeader title="审计日志" description={SYSTEM_AUDIT_PAGE_DESC} />
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
      </div>
      {list.loading ? (
        <p className="text-sm text-ink-muted">加载中…</p>
      ) : (
        <>
          <ul className="card divide-y text-sm">
            {list.items.length === 0 && <li className="px-4 py-8 text-center text-ink-faint">暂无审计记录</li>}
            {list.items.map((log: TenantAuditLog) => (
              <li key={log.id} className="px-4 py-3">
                <div className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
                  <span>{log.created_at.slice(0, 19).replace("T", " ")}</span>
                  <span className="font-medium text-brand">{auditActionLabel(log.action, auditMeta)}</span>
                  {log.resource_type && (
                    <span>
                      {auditResourceTypeLabel(log.resource_type, auditMeta)}
                      {log.resource_id ? ` · ${log.resource_id.slice(0, 8)}…` : ""}
                    </span>
                  )}
                </div>
                {log.ip_address && <p className="mt-1 text-xs text-ink-faint">IP {log.ip_address}</p>}
              </li>
            ))}
          </ul>
          <ResourceListFooter className="mt-3" page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
        </>
      )}
    </div>
  );
}
