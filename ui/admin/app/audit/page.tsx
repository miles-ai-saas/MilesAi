"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { adminApi, type AuditLog } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export default function AuditPage() {
  const ready = useRequireAdmin();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [actionFilter, setActionFilter] = useState("");
  const [tenantFilter, setTenantFilter] = useState("");
  const [exporting, setExporting] = useState(false);

  const load = async () => {
    const res = await adminApi.listAuditLogs({
      action: actionFilter.trim() || undefined,
      tenant_id: tenantFilter.trim() || undefined,
    });
    setLogs(res.items);
  };

  useEffect(() => {
    if (!ready) return;
    load().catch(() => undefined);
  }, [ready, actionFilter, tenantFilter]);

  const onExport = async () => {
    setExporting(true);
    try {
      await adminApi.exportAuditLogs({
        action: actionFilter.trim() || undefined,
        tenant_id: tenantFilter.trim() || undefined,
      });
    } catch {
      /* 403 等由 interceptor 处理 */
    } finally {
      setExporting(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="审计日志"
        description="平台级操作与敏感行为记录"
        action={
          <button type="button" className="btn-secondary" disabled={exporting} onClick={onExport}>
            {exporting ? "导出中…" : "导出 CSV"}
          </button>
        }
      />

      <div className="mb-4 flex flex-wrap gap-2">
        <input
          className="input-field max-w-xs"
          placeholder="action 精确匹配，如 tenant.create"
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
        />
        <input
          className="input-field max-w-xs"
          placeholder="租户 ID"
          value={tenantFilter}
          onChange={(e) => setTenantFilter(e.target.value)}
        />
      </div>

      <section className="card p-4">
        <ul className="max-h-[32rem] space-y-2 overflow-y-auto text-sm">
          {logs.length === 0 && <li className="text-ink-faint">暂无审计记录</li>}
          {logs.map((l) => (
            <li key={l.id} className="rounded-lg border border-line-soft bg-surface-muted px-3 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs text-ink-faint">
                  {l.created_at.slice(0, 19)}
                </span>
                <span className="font-medium text-ink">{l.action}</span>
                {l.tenant_id && (
                  <span className="badge bg-brand/10 text-brand">
                    租户 {l.tenant_id.slice(0, 8)}…
                  </span>
                )}
                {l.ip_address && <span className="text-xs text-ink-muted">{l.ip_address}</span>}
              </div>
              {Object.keys(l.detail || {}).length > 0 && (
                <pre className="mt-1 overflow-x-auto text-xs text-ink-muted">
                  {JSON.stringify(l.detail, null, 2)}
                </pre>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
