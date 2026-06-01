"use client";

import { FinancePageView, useFinancePage } from "@/features/finance";

export default function BusinessFinancePage() {
  const vm = useFinancePage();
  return <FinancePageView vm={vm} />;
}
