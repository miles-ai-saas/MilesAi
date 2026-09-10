"use client";

import {
  BillingPlanDetailAside,
  BillingPlanDetailFormSections,
  BillingPlanDetailHeaderSection,
  BillingPlanDetailStatsSection,
} from "@/features/billing/components/BillingPlanDetailSections";
import type { BillingPlanDetailPageVm } from "@/features/billing/hooks/use-billing-plan-detail-page";

export function BillingPlanDetailPageView({ vm }: { vm: BillingPlanDetailPageVm }) {
  const { plan, form, msg, err } = vm;

  if (!plan || !form) {
    return <p className="text-sm cell-muted">加载中…</p>;
  }

  return (
    <div className="admin-page-stack">
      <BillingPlanDetailHeaderSection vm={vm} />

      {msg && <p className="text-sm text-emerald-600">{msg}</p>}
      {err && <p className="text-sm text-red-600">{err}</p>}

      <BillingPlanDetailStatsSection vm={vm} />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <BillingPlanDetailFormSections vm={vm} />
        </div>
        <BillingPlanDetailAside vm={vm} />
      </div>
    </div>
  );
}
