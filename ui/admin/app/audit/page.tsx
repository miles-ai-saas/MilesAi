"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ListFooter } from "@/components/list/ListFooter";
import { PageHeader } from "@/components/layout/PageHeader";
import { usePagedList } from "@/hooks/use-paged-list";
import { auditActionLabel, auditActionOptions, auditDateRangeFromPreset, type AuditDatePreset } from "@/lib/audit-labels";
import { adminApi } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

const DATE_PRESETS: { value: AuditDatePreset; label: string }[] = [
  { value: "all", label: "全部时间" },
  { value: "today", label: "今天" },
  { value: "7d", label: "近 7 天" },
  { value: "30d", label: "近 30 天" },
  { value: "custom", label: "自定义" },
];

export default function AuditPage() {
  const ready = useRequireAdmin();
  const searchParams = useSearchParams();
  const [actionFilter, setActionFilter] = useState("");
  const [adminFilter, setAdminFilter] = useState("");
  const [tenantFilter, setTenantFilter] = useState("");
  const [datePreset, setDatePreset] = useState<AuditDatePreset>("30d");
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");
  const [metaActions, setMetaActions] = useState<string[]>([]);
  const [metaAdmins, setMetaAdmins] = useState<{ id: string; username: string }[]>([]);
  useEffect(() => {
    const fromUrl = searchParams.get("tenant_id");
    if (fromUrl) setTenantFilter(fromUrl);
  }, [searchParams]);

  useEffect(() => {
    if (!ready) return;
    adminApi
      .getAuditMeta()
      .then((m) => {
        setMetaActions(m.actions);
        setMetaAdmins(m.admins);
      })
      .catch(() => undefined);
  }, [ready]);

  const dateRange = useMemo(() => auditDateRangeFromPreset(datePreset, customFrom, customTo), [datePreset, customFrom, customTo]);

  const filterKey = `${actionFilter}-${adminFilter}-${tenantFilter.trim()}-${datePreset}-${customFrom}-${customTo}`;

  const list = usePagedList(
    useCallback(
      (p, s) =>
        adminApi.listAuditLogs({
          page: p,
          size: s,
          action: actionFilter || undefined,
          admin_id: adminFilter || undefined,
          tenant_id: tenantFilter.trim() || undefined,
          created_from: dateRange.created_from,
          created_to: dateRange.created_to,
        }),
      [actionFilter, adminFilter, tenantFilter, dateRange.created_from, dateRange.created_to],
    ),
    { enabled: ready, resetKey: filterKey },
  );

  const actionOptions = useMemo(() => auditActionOptions(metaActions), [metaActions]);

  return (
    <div>
      <PageHeader title="审计日志" description="平台级操作记录，支持按操作人、时间与租户追溯（私有化合规）" />

      <div className="mb-4 flex flex-wrap items-end gap-2">
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
            {DATE_PRESETS.map((p) => (
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
                    <span className="admin-data-meta">{l.created_at.slice(0, 19).replace("T", " ")}</span>
                    <span className="cell-primary">{auditActionLabel(l.action)}</span>
                    <span className="admin-data-meta cell-mono">{l.action}</span>
                    {l.admin_username && <span className="badge bg-brand-light text-ink">{l.admin_username}</span>}
                    {l.tenant_id && <span className="badge bg-brand/10 text-brand">租户 {l.tenant_id.slice(0, 8)}…</span>}
                    {l.ip_address && <span className="admin-data-meta">{l.ip_address}</span>}
                  </div>
                  {Object.keys(l.detail || {}).length > 0 && <pre className="admin-code-block">{JSON.stringify(l.detail, null, 2)}</pre>}
                </li>
              ))}
            </ul>
            <ListFooter className="mt-3" page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
          </>
        )}
      </section>
    </div>
  );
}
