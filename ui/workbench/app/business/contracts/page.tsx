"use client";

import { ContractsPageView, useContractsPage } from "@/features/contracts";

export default function ContractsListPage() {
  const vm = useContractsPage();
  return <ContractsPageView vm={vm} />;
}
