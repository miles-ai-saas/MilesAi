"use client";

import { BillingBillsPageView } from "@/components/billing/BillingBillsPageView";
import { useBillingBillsPage } from "@/hooks/use-billing-bills-page";

export default function BillingBillsPage() {
  const vm = useBillingBillsPage();
  return <BillingBillsPageView vm={vm} />;
}
