"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ListFooter } from "@/components/list/ListFooter";
import { PageHeader } from "@/components/layout/PageHeader";
import { usePagedList } from "@/hooks/use-paged-list";
import { adminApi } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export default function AuditPage() {
  const ready = useRequireAdmin();
  const searchParams = useSearchParams();
  const [actionFilter, setActionFilter] = useState("");
  const [tenantFilter, setTenantFilter] = useState("");
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    const fromUrl = searchParams.get("tenant_id");
    if (fromUrl) setTenantFilter(fromUrl);
  }, [searchParams]);

  const filterKey = `${actionFilter.trim()}-${tenantFilter.trim()}`;

  const list = usePagedList(
    useCallback(
      (p, s) =>
        adminApi.listAuditLogs({
          page: p,
          size: s,
          action: actionFilter.trim() || undefined,
          tenant_id: tenantFilter.trim() || undefined,
        }),
      [actionFilter, tenantFilter],
    ),
    { enabled: ready, resetKey: filterKey },
  );

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
        {list.loading ? (
          <p className="text-sm text-ink-muted">加载中…</p>
        ) : (
          <>
            <ul className="admin-data-list max-h-[32rem] overflow-y-auto">
              {list.items.length === 0 && <li className="text-ink-faint">暂无审计记录</li>}
              {list.items.map((l) => (
                <li key={l.id} className="admin-data-row">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="admin-data-meta">{l.created_at.slice(0, 19)}</span>
                    <span className="cell-primary">{l.action}</span>
                    {l.tenant_id && (
                      <span className="badge bg-brand/10 text-brand">
                        租户 {l.tenant_id.slice(0, 8)}…
                      </span>
                    )}
                    {l.ip_address && <span className="admin-data-meta">{l.ip_address}</span>}
                  </div>
                  {Object.keys(l.detail || {}).length > 0 && (
                    <pre className="admin-code-block">{JSON.stringify(l.detail, null, 2)}</pre>
                  )}
                </li>
              ))}
            </ul>
            <ListFooter
              className="mt-3"
              page={list.page}
              size={list.size}
              total={list.total}
              onPageChange={list.setPage}
              onSizeChange={list.setSize}
            />
          </>
        )}
      </section>
    </div>
  );
}
