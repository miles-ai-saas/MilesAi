"use client";

import { BillingPlanDetailPageView } from "@/features/billing/components/BillingPlanDetailPageView";
import { useBillingPlanDetailPage } from "@/features/billing/hooks/use-billing-plan-detail-page";

export default function BillingPlanDetailPage({ id }: { id: string }) {
  const vm = useBillingPlanDetailPage(id);
  return <BillingPlanDetailPageView vm={vm} />;
}
