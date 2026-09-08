"use client";

export default function BillingBillsPage() {
  const vm = useBillingBillsPage();
  return <BillingBillsPageView vm={vm} />;
}
import { BillingBillsPageView, useBillingBillsPage } from "@/features/billing";
