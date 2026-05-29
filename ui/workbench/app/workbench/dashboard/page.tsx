"use client";

/** 工作台概览（链路 §15）：`api.getWorkbenchOverview` + 快捷入口。 */

import { DashboardOverview } from "@/components/dashboard/DashboardOverview";
import { useDashboardPage } from "@/hooks/use-dashboard-page";

export default function WorkbenchOverviewPage() {
  const vm = useDashboardPage();
  return <DashboardOverview vm={vm} />;
}
