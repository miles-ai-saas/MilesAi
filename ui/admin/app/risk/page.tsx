"use client";

export default function RiskPage() {
  const vm = useRiskPage();
  return <RiskPageView vm={vm} />;
}
import { RiskPageView, useRiskPage } from "@/features/risk";
