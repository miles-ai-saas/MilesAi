"use client";

export default function BillingPlansPage() {
  const vm = useBillingPlansPage();
  return <BillingPlansPageView vm={vm} />;
}
import { BillingPlansPageView, useBillingPlansPage } from "@/features/billing";
