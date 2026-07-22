"use client";

/** 监控大盘（链路 §14）：统计/趋势/健康 + `useMonitorMeta`。 */

import {
  MonitorAlertsTab,
  MonitorHealthTab,
  MonitorOverviewTab,
  MonitorPageLayout,
  MonitorTrendsHeaderAction,
  MonitorTrendsTab,
  MonitorUsageTab,
  useMonitorPage,
} from "@/features/monitor";

function TabLoading() {
  return <p className="col-span-full py-12 text-center text-sm text-ink-muted animate-pulse">加载中…</p>;
}

export default function MonitorPage() {
  const vm = useMonitorPage();

  const headerAction = vm.tab === "trends" ? <MonitorTrendsHeaderAction vm={vm} /> : undefined;

  const isTabLoading = vm.tabLoading[vm.tab] ?? false;

  return (
    <MonitorPageLayout vm={vm} headerAction={headerAction}>
      {isTabLoading ? (
        <TabLoading />
      ) : (
        <>
          {vm.tab === "overview" && vm.report ? <MonitorOverviewTab vm={vm} /> : null}
          {vm.tab === "trends" && vm.report && vm.trends ? <MonitorTrendsTab vm={vm} /> : null}
          {vm.tab === "usage" ? <MonitorUsageTab vm={vm} /> : null}
          {vm.tab === "health" ? <MonitorHealthTab vm={vm} /> : null}
          {vm.tab === "alerts" ? <MonitorAlertsTab vm={vm} /> : null}
        </>
      )}
    </MonitorPageLayout>
  );
}
