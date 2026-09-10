"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { BillingPlansCreateSection, BillingPlansGridSection } from "@/features/billing/components/BillingPlansSections";
import type { BillingPlansPageVm } from "@/features/billing/hooks/use-billing-plans-page";
import { BILLING_PLANS_PAGE_DESCRIPTION } from "@/features/billing/lib/billing-plans-page-shared";

export function BillingPlansPageView({ vm }: { vm: BillingPlansPageVm }) {
  const { showPlanForm, setShowPlanForm, msg, err } = vm;

  return (
    <div className="admin-page-stack">
      <PageHeader
        title="套餐管理"
        description={BILLING_PLANS_PAGE_DESCRIPTION}
        action={
          <button type="button" className="btn-primary" onClick={() => setShowPlanForm((v) => !v)}>
            {showPlanForm ? "取消" : "新建套餐"}
          </button>
        }
      />

      {msg && <p className="admin-alert-ok">{msg}</p>}
      {err && <p className="admin-alert-err">{err}</p>}

      <BillingPlansCreateSection vm={vm} />
      <BillingPlansGridSection vm={vm} />
    </div>
  );
}
