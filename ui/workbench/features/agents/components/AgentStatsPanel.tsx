"use client";

/** 智能体统计（链路 §5，`api.getAgentStats`）。 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { SimpleLineChart } from "@/components/charts/SimpleLineChart";
import { Pagination } from "@/components/ui/Pagination";
import { StatChip } from "@/components/ui/StatChip";
import { api } from "@/lib/api";
import type { AgentStats, AgentStatsPoint } from "@/lib/types";
import { DEFAULT_PAGE_SIZE } from "@/lib/pagination";

const DAY_OPTIONS = [3, 7, 15, 30, 90] as const;

type DayOption = (typeof DAY_OPTIONS)[number];
type StatsView = "chart" | "table";

const VIEW_OPTIONS: { id: StatsView; label: string }[] = [
  { id: "chart", label: "趋势" },
  { id: "table", label: "明细" },
];

const METRICS = [
  {
    key: "sessions" as const,
    label: "会话数",
    totalKey: "sessions_total" as const,
    seriesKey: "sessions_by_day" as const,
    color: "#3B82F6",
    formatTotal: (v: number) => String(v),
  },
  {
    key: "active_users" as const,
    label: "活跃用户",
    totalKey: "active_users_total" as const,
    seriesKey: "active_users_by_day" as const,
    color: "#22C55E",
    formatTotal: (v: number) => String(v),
  },
  {
    key: "messages" as const,
    label: "消息数",
    totalKey: "messages_total" as const,
    seriesKey: "messages_by_day" as const,
    color: "#6366F1",
    formatTotal: (v: number) => String(v),
  },
  {
    key: "avg_rounds" as const,
    label: "平均对话轮次",
    totalKey: "avg_rounds_total" as const,
    seriesKey: "avg_rounds_by_day" as const,
    color: "#EC4899",
    formatTotal: (v: number) => v.toFixed(1),
  },
] as const;

type MetricKey = (typeof METRICS)[number]["key"];

type DailyRow = {
  date: string;
  sessions: number;
  activeUsers: number;
  messages: number;
  avgRounds: number;
};

function formatChartLabel(isoDate: string): string {
  const parts = isoDate.split("-");
  if (parts.length >= 3) return `${parts[1]}-${parts[2]}`;
  return isoDate.slice(5) || isoDate;
}

function toChartPoints(series: AgentStatsPoint[]) {
  return series.map((p) => ({
    label: formatChartLabel(p.date),
    value: p.value,
  }));
}

function buildDailyRows(stats: AgentStats): DailyRow[] {
  const len = stats.sessions_by_day.length;
  const rows: DailyRow[] = [];
  for (let i = 0; i < len; i++) {
    rows.push({
      date: stats.sessions_by_day[i].date,
      sessions: stats.sessions_by_day[i].value,
      activeUsers: stats.active_users_by_day[i]?.value ?? 0,
      messages: stats.messages_by_day[i]?.value ?? 0,
      avgRounds: stats.avg_rounds_by_day[i]?.value ?? 0,
    });
  }
  return rows.reverse();
}

function formatTableDate(isoDate: string): string {
  const parts = isoDate.split("-");
  if (parts.length >= 3) return `${parts[0]}-${parts[1]}-${parts[2]}`;
  return isoDate;
}

function ViewToggle({ view, onChange }: { view: StatsView; onChange: (view: StatsView) => void }) {
  return (
    <div className="inline-flex rounded-lg border border-line bg-surface p-0.5" role="tablist" aria-label="展示方式">
      {VIEW_OPTIONS.map((option) => (
        <button
          key={option.id}
          type="button"
          role="tab"
          aria-selected={view === option.id}
          onClick={() => onChange(option.id)}
          className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
            view === option.id ? "bg-brand text-white shadow-sm" : "text-ink-muted hover:bg-surface-muted hover:text-ink"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function DaySelector({ days, onChange }: { days: DayOption; onChange: (days: DayOption) => void }) {
  return (
    <div className="inline-flex rounded-lg border border-line bg-surface p-0.5" role="tablist" aria-label="统计时间范围">
      {DAY_OPTIONS.map((d) => (
        <button
          key={d}
          type="button"
          role="tab"
          aria-selected={days === d}
          onClick={() => onChange(d)}
          className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
            days === d ? "bg-brand text-white shadow-sm" : "text-ink-muted hover:bg-surface-muted hover:text-ink"
          }`}
        >
          {d}天
        </button>
      ))}
    </div>
  );
}

function StatsTrendChart({
  stats,
  days,
  metric,
  onMetricChange,
}: {
  stats: AgentStats;
  days: DayOption;
  metric: MetricKey;
  onMetricChange: (metric: MetricKey) => void;
}) {
  const active = METRICS.find((m) => m.key === metric) ?? METRICS[0];

  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-line bg-surface shadow-card">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-line-soft px-4 py-3">
        <div className="inline-flex flex-wrap gap-1 rounded-lg border border-line bg-surface-subtle p-0.5" role="tablist" aria-label="趋势指标">
          {METRICS.map((m) => (
            <button
              key={m.key}
              type="button"
              role="tab"
              aria-selected={metric === m.key}
              onClick={() => onMetricChange(m.key)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                metric === m.key ? "bg-surface text-ink shadow-sm ring-1 ring-line" : "text-ink-muted hover:text-ink"
              }`}
              style={metric === m.key ? { color: m.color } : undefined}
            >
              {m.label}
            </button>
          ))}
        </div>
        <div className="text-right">
          <p className="text-[11px] text-ink-faint">近 {days} 天合计</p>
          <p className="text-2xl font-bold tabular-nums" style={{ color: active.color }}>
            {active.formatTotal(stats[active.totalKey])}
          </p>
        </div>
      </div>
      <div className="min-h-0 flex-1 px-4 py-3">
        <SimpleLineChart
          key={active.key}
          points={toChartPoints(stats[active.seriesKey])}
          color={active.color}
          fill
          xLabelsBelow
        />
      </div>
    </section>
  );
}

function StatsDailyTable({ rows }: { rows: DailyRow[] }) {
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(DEFAULT_PAGE_SIZE);

  useEffect(() => {
    setPage(1);
  }, [rows]);

  const pageRows = useMemo(() => {
    const start = (page - 1) * size;
    return rows.slice(start, start + size);
  }, [rows, page, size]);

  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="mb-2 flex shrink-0 items-baseline justify-between gap-3">
        <h3 className="text-sm font-semibold text-ink">每日明细</h3>
        <span className="text-xs text-ink-faint">{rows.length} 天 · 最新在前</span>
      </div>
      <div className="min-h-0 flex-1 overflow-auto rounded-xl border border-line bg-surface shadow-card">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="sticky top-0 z-[1] border-b border-line bg-surface-muted text-xs text-ink-muted">
            <tr>
              <th className="whitespace-nowrap px-4 py-3 font-medium">日期</th>
              <th className="whitespace-nowrap px-4 py-3 text-right font-medium">会话数</th>
              <th className="whitespace-nowrap px-4 py-3 text-right font-medium">活跃用户</th>
              <th className="whitespace-nowrap px-4 py-3 text-right font-medium">消息数</th>
              <th className="whitespace-nowrap px-4 py-3 text-right font-medium">平均轮次</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line-soft">
            {rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-12 text-center text-ink-faint">
                  暂无统计数据
                </td>
              </tr>
            ) : (
              pageRows.map((row) => (
                <tr key={row.date} className="hover:bg-surface-muted/40">
                  <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-ink">{formatTableDate(row.date)}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-ink">{row.sessions}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-ink">{row.activeUsers}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-ink">{row.messages}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-ink-muted">{row.avgRounds.toFixed(1)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {rows.length > 0 ? (
        <div className="shrink-0 pt-2.5">
          <Pagination
            page={page}
            size={size}
            total={rows.length}
            onPageChange={setPage}
            onSizeChange={(nextSize) => {
              setSize(nextSize);
              setPage(1);
            }}
            pageSizeOptions={[10, 15, 30, 90]}
          />
        </div>
      ) : null}
    </section>
  );
}

type Props = {
  agentId: string;
};

export function AgentStatsPanel({ agentId }: Props) {
  const [days, setDays] = useState<DayOption>(7);
  const [view, setView] = useState<StatsView>("chart");
  const [metric, setMetric] = useState<MetricKey>("sessions");
  const [stats, setStats] = useState<AgentStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const dailyRows = useMemo(() => (stats ? buildDailyRows(stats) : []), [stats]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getAgentStats(agentId, days);
      setStats(data);
    } catch (e) {
      setStats(null);
      setError(e instanceof Error ? e.message : "加载统计失败");
    } finally {
      setLoading(false);
    }
  }, [agentId, days]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-line-soft bg-surface-subtle/50 px-6 py-2.5">
        <p className="text-xs text-ink-muted">近 {days} 天汇总</p>
        <div className="flex flex-wrap items-center gap-2">
          <ViewToggle view={view} onChange={setView} />
          <DaySelector days={days} onChange={setDays} />
        </div>
      </div>

      {loading && !stats ? (
        <p className="flex flex-1 items-center justify-center text-sm text-ink-muted">加载统计数据…</p>
      ) : error ? (
        <div className="flex flex-1 flex-col items-center justify-center">
          <p className="text-sm text-ink-muted">{error}</p>
          <button type="button" className="btn-sm-outline mt-3" onClick={() => void load()}>
            重试
          </button>
        </div>
      ) : stats ? (
        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden px-6 py-4">
          {view === "table" ? (
            <div className="grid shrink-0 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {METRICS.map((m) => (
                <StatChip key={m.key} label={m.label} value={m.formatTotal(stats[m.totalKey])} />
              ))}
            </div>
          ) : null}

          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            {view === "chart" ? (
              <StatsTrendChart stats={stats} days={days} metric={metric} onMetricChange={setMetric} />
            ) : (
              <StatsDailyTable rows={dailyRows} />
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
