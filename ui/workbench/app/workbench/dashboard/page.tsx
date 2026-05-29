"use client";

/** 工作台概览（链路 §15）：`api.getWorkbenchOverview` + 快捷入口。 */

import { DashboardOverview, useDashboardPage } from "@/features/dashboard";

export default function WorkbenchOverviewPage() {
  const vm = useDashboardPage();
  return <DashboardOverview vm={vm} />;
}
