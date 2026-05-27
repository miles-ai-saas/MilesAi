"use client";

/** 智能体统计（链路 §5，`api.getAgentStats`）。 */
import { useCallback, useEffect, useState } from "react";
import { SimpleLineChart } from "@/components/charts/SimpleLineChart";
import { api } from "@/lib/api";
import type { AgentStats, AgentStatsPoint } from "@/lib/types";

const DAY_OPTIONS = [3, 7, 15, 30, 90] as const;

type DayOption = (typeof DAY_OPTIONS)[number];

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
    color: "#3B82F6",
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
];

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

function StatsMetricCard({
  label,
  total,
  color,
  series,
}: {
  label: string;
  total: string;
  color: string;
  series: AgentStatsPoint[];
}) {
  return (
    <article className="flex flex-col rounded-xl border border-line bg-surface px-4 py-3 shadow-card">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-medium text-ink">{label}</h3>
        <span className="text-xl font-bold tabular-nums" style={{ color }}>
          {total}
        </span>
      </div>
      <div className="mt-2">
        <SimpleLineChart points={toChartPoints(series)} color={color} height={112} />
      </div>
    </article>
  );
}

type Props = {
  agentId: string;
};

export function AgentStatsPanel({ agentId }: Props) {
  const [days, setDays] = useState<DayOption>(7);
  const [stats, setStats] = useState<AgentStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-line-soft bg-surface-subtle/60 px-6 py-3.5 pr-14">
        <h2 id="workbench-overlay-title" className="text-base font-semibold text-ink">
          数据概览
        </h2>
        <div
          className="inline-flex rounded-lg border border-line bg-surface p-0.5"
          role="tablist"
          aria-label="统计时间范围"
        >
          {DAY_OPTIONS.map((d) => (
            <button
              key={d}
              type="button"
              role="tab"
              aria-selected={days === d}
              onClick={() => setDays(d)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                days === d
                  ? "bg-brand text-white shadow-sm"
                  : "text-ink-muted hover:bg-surface-muted hover:text-ink"
              }`}
            >
              {d}天
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
        {loading && !stats ? (
          <p className="py-14 text-center text-sm text-ink-muted">加载统计数据…</p>
        ) : error ? (
          <div className="py-14 text-center">
            <p className="text-sm text-ink-muted">{error}</p>
            <button type="button" className="btn-sm-outline mt-3" onClick={() => void load()}>
              重试
            </button>
          </div>
        ) : stats ? (
          <div className="mx-auto grid w-full max-w-5xl gap-4 sm:grid-cols-2">
            {METRICS.map((m) => (
              <StatsMetricCard
                key={m.key}
                label={m.label}
                total={m.formatTotal(stats[m.totalKey])}
                color={m.color}
                series={stats[m.seriesKey]}
              />
            ))}
          </div>
        ) : null}
        {!loading && stats && (
          <p className="mt-4 text-center text-[11px] text-ink-faint">
            服务端会话统计接入后将在此展示真实趋势；当前为按日时间轴占位。
          </p>
        )}
      </div>
    </div>
  );
}
