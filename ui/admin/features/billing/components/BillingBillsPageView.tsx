"use client";

import { BillingBillsGenerateSection, BillingBillsTableSection } from "@/features/billing/components/BillingBillsSections";
import { PageHeader } from "@/components/layout/PageHeader";
import type { BillingBillsPageVm } from "@/features/billing/hooks/use-billing-bills-page";
import { BILLING_BILLS_PAGE_DESCRIPTION } from "@/features/billing/lib/billing-bills-page-shared";

export function BillingBillsPageView({ vm }: { vm: BillingBillsPageVm }) {
  const { msg, err } = vm;

  return (
    <div>
      <PageHeader title="账单管理" description={BILLING_BILLS_PAGE_DESCRIPTION} />

      {msg && <p className="mb-4 text-sm text-emerald-600">{msg}</p>}
      {err && <p className="mb-4 text-sm text-red-600">{err}</p>}

      <BillingBillsGenerateSection vm={vm} />
      <BillingBillsTableSection vm={vm} />
    </div>
  );
}
