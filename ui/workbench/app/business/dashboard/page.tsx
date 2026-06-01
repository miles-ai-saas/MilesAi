"use client";

import { BusinessDashboardView, useBusinessDashboardPage } from "@/features/business-dashboard";

export default function BusinessDashboardPage() {
  const vm = useBusinessDashboardPage();
  return <BusinessDashboardView vm={vm} />;
}
