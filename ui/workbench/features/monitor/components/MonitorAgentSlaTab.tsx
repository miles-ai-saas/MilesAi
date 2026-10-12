"use client";

import Link from "next/link";
import { SimpleBarChart } from "@/components/charts/SimpleBarChart";
import { StatChip } from "@/components/ui/StatChip";
import type { MonitorPageVm } from "@/features/monitor/hooks/use-monitor-page";
import type { AgentSlaRouteRow } from "@/lib/types";

function fmtMs(n: number): string {
  if (!Number.isFinite(n)) return "—";
  return `${Math.round(n)} ms`;
}

function fmtRate(n: number): string {
  if (!Number.isFinite(n)) return "—";
  return `${n.toFixed(1)}%`;
}

function RouteTable({ rows }: { rows: AgentSlaRouteRow[] }) {
  if (!rows.length) {
    return <p className="rounded-xl border border-dashed border-line py-10 text-center text-sm text-ink-faint">暂无数据</p>;
  }
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-surface shadow-card">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead className="border-b border-line-soft bg-surface-muted text-xs text-ink-muted">
          <tr>
            <th className="px-4 py-2 font-medium">路由</th>
            <th className="px-4 py-2 font-medium">调用</th>
            <th className="px-4 py-2 font-medium">成功率</th>
            <th className="px-4 py-2 font-medium">P50</th>
            <th className="px-4 py-2 font-medium">P95</th>
            <th className="px-4 py-2 font-medium">平均延迟</th>
            <th className="px-4 py-2 font-medium">Token/次</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.route} className="border-b border-line-soft">
              <td className="px-4 py-2 font-medium text-ink">{row.route}</td>
              <td className="px-4 py-2 tabular-nums">{row.call_count}</td>
              <td className="px-4 py-2 tabular-nums">{fmtRate(row.success_rate)}</td>
              <td className="px-4 py-2 tabular-nums">{fmtMs(row.latency_p50_ms)}</td>
              <td className="px-4 py-2 tabular-nums">{fmtMs(row.latency_p95_ms)}</td>
              <td className="px-4 py-2 tabular-nums">{fmtMs(row.latency_avg_ms)}</td>
              <td className="px-4 py-2 tabular-nums">{Math.round(row.tokens_per_call_avg)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function MonitorAgentSlaTab({ vm }: { vm: MonitorPageVm }) {
  const { agentSla, trendDays } = vm;
  if (!agentSla) {
    return <p className="col-span-full py-12 text-center text-sm text-ink-muted">暂无 SLA 数据</p>;
  }

  const o = agentSla.overview;

  return (
    <div className="col-span-full space-y-5">
      <p className="text-xs text-ink-muted">
        近 {trendDays} 天 · 数据来自对话调用流水（agt_agent_chat_calls），与智能体「调用记录」同口径。
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatChip
          label="调用次数"
          value={String(o.call_count)}
          hint={`成功 ${o.success_count} · 失败 ${o.failed_count} · 拦截 ${o.blocked_count}`}
        />
        <StatChip label="成功率" value={fmtRate(o.success_rate)} hint="success / 全部调用" />
        <StatChip
          label="P95 延迟"
          value={fmtMs(o.latency_p95_ms)}
          hint={`P50 ${fmtMs(o.latency_p50_ms)} · 平均 ${fmtMs(o.latency_avg_ms)}`}
        />
        <StatChip label="Token / 次" value={String(Math.round(o.tokens_per_call_avg))} hint={`合计 ${o.total_tokens}`} />
      </div>

      <section className="rounded-xl border border-line bg-surface p-5 shadow-card">
        <h3 className="text-sm font-semibold text-ink">调用量趋势</h3>
        <p className="mt-1 text-xs text-ink-muted">按日调用次数</p>
        <div className="mt-4">
          {agentSla.by_day.length === 0 ? (
            <p className="text-xs text-ink-faint">暂无按日数据</p>
          ) : (
            <SimpleBarChart
              items={agentSla.by_day.map((d) => ({
                label: d.date.slice(5),
                value: d.call_count,
              }))}
            />
          )}
        </div>
      </section>

      <section className="space-y-2">
        <h3 className="text-sm font-semibold text-ink">按路由</h3>
        <RouteTable rows={agentSla.by_route} />
      </section>

      <section className="space-y-2">
        <h3 className="text-sm font-semibold text-ink">按智能体（调用量 Top）</h3>
        {agentSla.by_agent.length === 0 ? (
          <p className="rounded-xl border border-dashed border-line py-10 text-center text-sm text-ink-faint">暂无智能体调用</p>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-line bg-surface shadow-card">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="border-b border-line-soft bg-surface-muted text-xs text-ink-muted">
                <tr>
                  <th className="px-4 py-2 font-medium">智能体</th>
                  <th className="px-4 py-2 font-medium">调用</th>
                  <th className="px-4 py-2 font-medium">成功率</th>
                  <th className="px-4 py-2 font-medium">P50</th>
                  <th className="px-4 py-2 font-medium">P95</th>
                  <th className="px-4 py-2 font-medium">平均延迟</th>
                  <th className="px-4 py-2 font-medium">Token/次</th>
                </tr>
              </thead>
              <tbody>
                {agentSla.by_agent.map((row) => (
                  <tr key={row.agent_id} className="border-b border-line-soft">
                    <td className="px-4 py-2 font-medium text-ink">
                      <Link href={`/workbench/agents?id=${row.agent_id}`} className="text-brand hover:underline">
                        {row.agent_name || `${row.agent_id.slice(0, 8)}…`}
                      </Link>
                    </td>
                    <td className="px-4 py-2 tabular-nums">{row.call_count}</td>
                    <td className="px-4 py-2 tabular-nums">{fmtRate(row.success_rate)}</td>
                    <td className="px-4 py-2 tabular-nums">{fmtMs(row.latency_p50_ms)}</td>
                    <td className="px-4 py-2 tabular-nums">{fmtMs(row.latency_p95_ms)}</td>
                    <td className="px-4 py-2 tabular-nums">{fmtMs(row.latency_avg_ms)}</td>
                    <td className="px-4 py-2 tabular-nums">{Math.round(row.tokens_per_call_avg)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
