"use client";

import { SimpleBarChart } from "@/components/charts/SimpleBarChart";
import { ChartPanel } from "@/components/monitor/monitor-page-ui";
import type { MonitorPageVm } from "@/hooks/use-monitor-page";
import { documentStatusLabel } from "@/lib/document-status";
import { monitorTrendDayOptions } from "@/lib/monitor-labels";

export function MonitorTrendsTab({ vm }: { vm: MonitorPageVm }) {
  const { report, trends, trendDays, monitorMeta, kbMeta } = vm;
  if (!report || !trends) {
    return <p className="col-span-full py-12 text-center text-sm text-ink-muted">加载趋势数据…</p>;
  }

  const trendHint = monitorTrendDayOptions(monitorMeta).find((o) => o.value === String(trendDays))?.label ?? `近 ${trendDays} 天`;

  return (
    <div className="col-span-full space-y-5">
      <ChartPanel title="任务趋势" subtitle={`${trendHint}每日任务总量`}>
        {trends.task_by_day.length === 0 ? (
          <p className="text-xs text-ink-faint">暂无任务数据</p>
        ) : (
          <SimpleBarChart
            items={trends.task_by_day.map((d) => ({
              label: d.date.slice(5),
              value: d.total,
            }))}
          />
        )}
      </ChartPanel>

      <div className="grid gap-5 lg:grid-cols-2">
        <ChartPanel title="任务状态分布" subtitle="当前租户累计">
          <SimpleBarChart
            items={[
              { label: "成功", value: report.tasks.success, color: "#059669" },
              { label: "失败", value: report.tasks.failed, color: "#dc2626" },
              { label: "运行", value: report.tasks.running, color: "#d97706" },
              { label: "等待", value: report.tasks.pending, color: "#6b7280" },
            ]}
          />
        </ChartPanel>
        <ChartPanel title="合规拦截趋势" subtitle={`${trendHint}按日统计`}>
          {trends.intercept_by_day.length === 0 ? (
            <p className="text-xs text-ink-faint">暂无拦截数据</p>
          ) : (
            <SimpleBarChart
              items={trends.intercept_by_day.map((d) => ({
                label: String(d.date).slice(5),
                value: d.count,
                color: "#dc2626",
              }))}
            />
          )}
        </ChartPanel>
      </div>

      <ChartPanel title="文档状态分布" subtitle="按处理状态汇总">
        {Object.keys(report.documents_by_status).length === 0 ? (
          <p className="text-xs text-ink-faint">暂无文档</p>
        ) : (
          <SimpleBarChart
            items={Object.entries(report.documents_by_status).map(([k, v]) => ({
              label: documentStatusLabel(k, kbMeta?.document_statuses),
              value: v,
            }))}
          />
        )}
      </ChartPanel>
    </div>
  );
}

export function MonitorTrendsHeaderAction({ vm }: { vm: MonitorPageVm }) {
  return (
    <select
      className="input-field w-auto shrink-0 text-sm"
      value={String(vm.trendDays)}
      onChange={(e) => vm.setTrendDays(Number(e.target.value) || 7)}
      aria-label="趋势天数"
    >
      {monitorTrendDayOptions(vm.monitorMeta).map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}
