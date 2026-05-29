"use client";

import { BillingPlansPageView } from "@/components/billing/BillingPlansPageView";
import { useBillingPlansPage } from "@/hooks/use-billing-plans-page";

export default function BillingPlansPage() {
  const vm = useBillingPlansPage();
  return <BillingPlansPageView vm={vm} />;
}
