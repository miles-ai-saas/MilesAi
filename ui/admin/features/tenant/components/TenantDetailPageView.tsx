"use client";

import { TenantDetailBillsSection, TenantDetailQuotaSection } from "@/features/tenant/components/TenantDetailMainSections";
import { TenantDetailHeaderSection, TenantDetailStatsSection } from "@/features/tenant/components/TenantDetailHeaderSection";
import { TenantDetailSubscriptionAside } from "@/features/tenant/components/TenantDetailSubscriptionAside";
import type { TenantDetailPageVm } from "@/features/tenant/hooks/use-tenant-detail-page";

export function TenantDetailPageView({ vm }: { vm: TenantDetailPageVm }) {
  const { tenant, msg, err } = vm;

  if (!tenant) {
    return <p className="text-sm cell-muted">加载中…</p>;
  }

  return (
    <div className="admin-page-stack">
      <TenantDetailHeaderSection vm={vm} />

      {msg && <p className="text-sm text-emerald-600">{msg}</p>}
      {err && <p className="text-sm text-red-600">{err}</p>}

      <TenantDetailStatsSection vm={vm} />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <TenantDetailQuotaSection vm={vm} />
          <TenantDetailBillsSection vm={vm} />
        </div>
        <TenantDetailSubscriptionAside vm={vm} />
      </div>
    </div>
  );
}
