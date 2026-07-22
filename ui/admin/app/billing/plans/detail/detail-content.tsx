"use client";

import { BillingPlanDetailPageView } from "@/components/billing/BillingPlanDetailPageView";
import { useBillingPlanDetailPage } from "@/hooks/use-billing-plan-detail-page";

export default function BillingPlanDetailPage({ id }: { id: string }) {
  const vm = useBillingPlanDetailPage(id);
  return <BillingPlanDetailPageView vm={vm} />;
}
