"use client";

import { ListFooter } from "@/components/list/ListFooter";
import type { AuditPageVm } from "@/features/audit/hooks/use-audit-page";
import {
  auditResourceTypeLabel,
  buildAdminAuditLogSummary,
  formatAuditTime,
  resolveAdminAuditOperatorLabel,
  shortenId,
} from "@/features/audit/lib/audit-log-present";
import { auditActionLabel } from "@/features/audit/lib/audit-labels";
import { AUDIT_DATE_PRESETS } from "@/features/audit/lib/audit-page-shared";
import type { AuditDatePreset } from "@/features/audit/lib/audit-labels";
import type { AuditLog } from "@/lib/api";

export function AuditFiltersSection({ vm }: { vm: AuditPageVm }) {
  const {
    actionFilter,
    setActionFilter,
    adminFilter,
    setAdminFilter,
    tenantFilter,
    setTenantFilter,
    datePreset,
    setDatePreset,
    customFrom,
    setCustomFrom,
    customTo,
    setCustomTo,
    metaAdmins,
    actionOptions,
  } = vm;

  return (
    <div className="admin-filter-bar items-end">
      <label className="flex flex-col gap-1">
        <span className="text-xs text-ink-muted">操作类型</span>
        <select className="input-field w-auto min-w-[10rem]" value={actionFilter} onChange={(e) => setActionFilter(e.target.value)}>
          {actionOptions.map((o) => (
            <option key={o.value || "all"} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-xs text-ink-muted">操作人</span>
        <select className="input-field w-auto min-w-[8rem]" value={adminFilter} onChange={(e) => setAdminFilter(e.target.value)}>
          <option value="">全部管理员</option>
          {metaAdmins.map((a) => (
            <option key={a.id} value={a.id}>
              {a.username}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-xs text-ink-muted">租户 ID</span>
        <input className="input-field w-auto min-w-[12rem]" placeholder="可选" value={tenantFilter} onChange={(e) => setTenantFilter(e.target.value)} />
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-xs text-ink-muted">时间范围</span>
        <select className="input-field w-auto min-w-[8rem]" value={datePreset} onChange={(e) => setDatePreset(e.target.value as AuditDatePreset)}>
          {AUDIT_DATE_PRESETS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
      </label>
      {datePreset === "custom" && (
        <>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-ink-muted">开始日期</span>
            <input type="date" className="input-field w-auto" value={customFrom} onChange={(e) => setCustomFrom(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-ink-muted">结束日期</span>
            <input type="date" className="input-field w-auto" value={customTo} onChange={(e) => setCustomTo(e.target.value)} />
          </label>
        </>
      )}
    </div>
  );
}

export function AuditLogListSection({ vm }: { vm: AuditPageVm }) {
  const { list, hasActiveFilters } = vm;

  return (
    <section className="card p-5">
      {list.loading ? (
        <p className="text-sm text-ink-muted">加载中…</p>
      ) : (
        <>
          <div className="admin-table-wrap border-0">
            <table className="admin-table">
              <thead>
                <tr>
                  <th className="col-compact">时间</th>
                  <th>操作人</th>
                  <th>动作</th>
                  <th>租户</th>
                  <th>资源</th>
                  <th className="col-compact">IP</th>
                  <th>说明</th>
                </tr>
              </thead>
              <tbody>
                {list.items.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-10 text-center cell-muted">
                      {hasActiveFilters ? "当前筛选条件下暂无审计记录" : "暂无审计记录"}
                    </td>
                  </tr>
                ) : (
                  list.items.map((log: AuditLog) => {
                    const operator = resolveAdminAuditOperatorLabel(log);
                    const summary = buildAdminAuditLogSummary(log);
                    return (
                      <tr key={log.id}>
                        <td className="col-compact cell-muted font-mono text-xs">{formatAuditTime(log.created_at)}</td>
                        <td className="cell-primary" title={operator.title}>
                          {operator.label}
                        </td>
                        <td>{auditActionLabel(log.action)}</td>
                        <td className="cell-muted" title={log.tenant_id ?? undefined}>
                          {log.tenant_id ? shortenId(log.tenant_id) : "—"}
                        </td>
                        <td className="cell-muted">
                          {log.resource_type ? (
                            <span title={log.resource_id ?? undefined}>
                              {auditResourceTypeLabel(log.resource_type)}
                              {log.resource_id ? ` · ${shortenId(log.resource_id)}` : ""}
                            </span>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="col-compact cell-muted font-mono text-xs">{log.ip_address ?? "—"}</td>
                        <td className="cell-muted" title={Object.keys(log.detail || {}).length > 0 ? JSON.stringify(log.detail) : undefined}>
                          {summary || "—"}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
          <ListFooter className="mt-3" page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
        </>
      )}
    </section>
  );
}
