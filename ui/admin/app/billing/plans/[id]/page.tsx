"use client";

import { BillingPlanDetailPageView } from "@/components/billing/BillingPlanDetailPageView";
import { useBillingPlanDetailPage } from "@/hooks/use-billing-plan-detail-page";

export default function BillingPlanDetailPage() {
  const vm = useBillingPlanDetailPage();
  return <BillingPlanDetailPageView vm={vm} />;
}
