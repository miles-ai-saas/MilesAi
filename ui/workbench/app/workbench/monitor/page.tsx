"use client";

/** 监控大盘（链路 §14）：统计/趋势/健康 + `useMonitorMeta`。 */

import { MonitorAlertsTab } from "@/components/monitor/MonitorAlertsTab";
import { MonitorHealthTab } from "@/components/monitor/MonitorHealthTab";
import { MonitorOverviewTab } from "@/components/monitor/MonitorOverviewTab";
import { MonitorPageLayout } from "@/components/monitor/MonitorPageLayout";
import { MonitorTrendsHeaderAction, MonitorTrendsTab } from "@/components/monitor/MonitorTrendsTab";
import { MonitorUsageTab } from "@/components/monitor/MonitorUsageTab";
import { useMonitorPage } from "@/hooks/use-monitor-page";

export default function MonitorPage() {
  const vm = useMonitorPage();

  const headerAction = vm.tab === "trends" ? <MonitorTrendsHeaderAction vm={vm} /> : undefined;

  return (
    <MonitorPageLayout vm={vm} headerAction={headerAction}>
      {vm.tab === "trends" ? <MonitorTrendsTab vm={vm} /> : null}
      {vm.tab === "usage" ? <MonitorUsageTab vm={vm} /> : null}
      {vm.tab === "health" ? <MonitorHealthTab vm={vm} /> : null}
      {vm.tab === "alerts" ? <MonitorAlertsTab vm={vm} /> : null}
      {vm.tab === "overview" && vm.report ? <MonitorOverviewTab vm={vm} /> : null}
    </MonitorPageLayout>
  );
}
