"use client";

import type { ReactNode } from "react";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import type { MonitorPageVm } from "@/features/monitor/hooks/use-monitor-page";
import type { MonitorTab } from "@/features/monitor/lib/monitor-shared";

const MONITOR_PAGE_DESC = "查看租户业务指标、异步任务与合规拦截趋势，检查依赖组件健康状态，并配置 Webhook 告警。";

const MONITOR_MAIN_TABS: { key: MonitorTab; label: string }[] = [
  { key: "overview", label: "概览" },
  { key: "trends", label: "趋势分析" },
  { key: "usage", label: "模型用量" },
  { key: "health", label: "系统健康" },
  { key: "alerts", label: "告警配置" },
];

type Props = {
  vm: MonitorPageVm;
  headerAction?: ReactNode;
  children: React.ReactNode;
};

export function MonitorPageLayout({ vm, headerAction, children }: Props) {
  const defaultHeader = (
    <div className="flex shrink-0 gap-2">
      <button type="button" onClick={() => void vm.reload()} className="btn-ghost text-sm" disabled={vm.loading}>
        {vm.loading ? "刷新中…" : "刷新"}
      </button>
      <button type="button" onClick={() => void vm.onExport()} className="btn-ghost text-sm" disabled={!vm.report}>
        导出 CSV
      </button>
    </div>
  );

  return (
    <ResourceListLayout
      title="监控"
      description={MONITOR_PAGE_DESC}
      tabs={MONITOR_MAIN_TABS}
      activeTab={vm.tab}
      onTabChange={vm.onTabChange}
      search=""
      onSearchChange={() => {}}
      showSearch={false}
      loading={vm.loading}
      headerAction={headerAction ?? defaultHeader}
    >
      {children}
    </ResourceListLayout>
  );
}
