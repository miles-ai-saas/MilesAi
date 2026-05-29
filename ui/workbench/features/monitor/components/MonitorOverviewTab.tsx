"use client";

import { SimpleBarChart } from "@/components/charts/SimpleBarChart";
import { StatChip } from "@/features/monitor/components/monitor-page-ui";
import type { MonitorPageVm } from "@/features/monitor/hooks/use-monitor-page";

export function MonitorOverviewTab({ vm }: { vm: MonitorPageVm }) {
  const { report, trends, statCards, setTab } = vm;
  if (!report) return null;

  return (
    <>
      <div className="col-span-full grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((c) => (
          <StatChip key={c.label} label={c.label} value={c.value} hint={c.hint} />
        ))}
      </div>
      <div className="col-span-full grid gap-4 lg:grid-cols-2">
        <section className="rounded-xl border border-line bg-surface p-5 shadow-card">
          <h3 className="text-sm font-semibold text-ink">任务概况</h3>
          {trends && trends.task_by_day.length > 0 ? (
            <SimpleBarChart
              className="mt-4"
              items={trends.task_by_day.slice(-5).map((d) => ({
                label: d.date.slice(5),
                value: d.total,
              }))}
            />
          ) : (
            <p className="mt-3 text-xs text-ink-faint">暂无近期任务数据</p>
          )}
          <button type="button" className="mt-4 text-xs text-brand hover:underline" onClick={() => setTab("trends")}>
            查看完整趋势 →
          </button>
        </section>
        <section className="rounded-xl border border-line bg-surface p-5 shadow-card">
          <h3 className="text-sm font-semibold text-ink">合规与文档</h3>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-ink-muted">今日拦截</dt>
              <dd className="font-semibold tabular-nums text-ink">{report.stats.intercept_logs_today}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-muted">待处理文档</dt>
              <dd className="font-semibold tabular-nums text-ink">{report.stats.pending_documents}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-muted">文档总数</dt>
              <dd className="font-semibold tabular-nums text-ink">{report.stats.documents}</dd>
            </div>
          </dl>
          <button type="button" className="mt-4 text-xs text-brand hover:underline" onClick={() => setTab("trends")}>
            查看趋势图表 →
          </button>
        </section>
      </div>
      <div className="col-span-full flex flex-wrap gap-3 rounded-xl border border-dashed border-line px-4 py-3">
        <button type="button" className="text-sm text-brand hover:underline" onClick={() => setTab("health")}>
          检查系统健康
        </button>
        <span className="text-ink-faint">·</span>
        <button type="button" className="text-sm text-brand hover:underline" onClick={() => setTab("alerts")}>
          配置告警 Webhook
        </button>
      </div>
    </>
  );
}
