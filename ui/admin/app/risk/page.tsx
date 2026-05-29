"use client";

import { RiskPageView } from "@/components/risk/RiskPageView";
import { useRiskPage } from "@/hooks/use-risk-page";

export default function RiskPage() {
  const vm = useRiskPage();
  return <RiskPageView vm={vm} />;
}
