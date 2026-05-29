"use client";

import { AdminDetailHeader } from "@/components/layout/AdminDetailHeader";
import type { TenantDetailPageVm } from "@/hooks/use-tenant-detail-page";
import { TENANT_STATUS_LABEL, tenantStatusBadgeClass, tenantUsagePct } from "@/lib/tenant-detail-shared";

export function TenantDetailHeaderSection({ vm }: { vm: TenantDetailPageVm }) {
  const { id, tenant, copyTenantId } = vm;
  if (!tenant) return null;

  return (
    <AdminDetailHeader
      backHref="/tenants"
      backLabel="返回租户列表"
      title={tenant.name}
      badges={
        <>
          <span className={`status-badge ${tenantStatusBadgeClass(tenant.status)}`}>{TENANT_STATUS_LABEL[tenant.status] ?? tenant.status}</span>
          {tenant.plan_name && <span className="badge bg-brand-light text-brand">{tenant.plan_name}</span>}
        </>
      }
      description={
        <>
          创建于 {tenant.created_at.slice(0, 10)}
          <span className="mx-2 text-ink-faint">·</span>
          <button type="button" className="font-mono text-xs text-ink-faint hover:text-brand" onClick={() => void copyTenantId()} title="点击复制">
            {id.slice(0, 8)}…
          </button>
        </>
      }
    />
  );
}

export function TenantDetailStatsSection({ vm }: { vm: TenantDetailPageVm }) {
  const { tenant } = vm;
  if (!tenant) return null;

  const tokenPct = tenantUsagePct(tenant.usage.tokens_used_month, tenant.max_tokens_monthly);
  const storagePct = tenantUsagePct(tenant.usage.storage_used_mb, tenant.max_storage_mb);

  const stats = [
    { label: "Token 本月", value: `${tokenPct}%`, sub: `${tenant.usage.tokens_used_month.toLocaleString()} 已用` },
    { label: "存储空间", value: `${storagePct}%`, sub: `${tenant.usage.storage_used_mb} / ${tenant.max_storage_mb} MB` },
    { label: "租户用户", value: String(tenant.usage.users), sub: "活跃用户账号" },
    {
      label: "资源实例",
      value: String(tenant.usage.knowledge_bases + tenant.usage.agents + tenant.usage.flows),
      sub: `KB ${tenant.usage.knowledge_bases} · 智能体 ${tenant.usage.agents} · 流程 ${tenant.usage.flows}`,
    },
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {stats.map((s) => (
        <div key={s.label} className="card p-4">
          <p className="text-xs cell-muted">{s.label}</p>
          <p className="mt-1 text-2xl font-bold stat-value text-brand">{s.value}</p>
          <p className="mt-1 text-xs cell-muted">{s.sub}</p>
        </div>
      ))}
    </div>
  );
}
