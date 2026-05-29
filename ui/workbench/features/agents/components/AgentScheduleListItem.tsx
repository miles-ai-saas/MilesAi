"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AgentSchedule, AgentScheduleRun } from "@/lib/types";

function formatScheduleTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function AgentScheduleRunsPanel({ agentId, scheduleId }: { agentId: string; scheduleId: string }) {
  const [runs, setRuns] = useState<AgentScheduleRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    void api
      .listAgentScheduleRuns(agentId, scheduleId, 1, 10)
      .then((res) => {
        if (!cancelled) setRuns(res.items);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "加载失败");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [agentId, scheduleId]);

  if (loading) {
    return <p className="mt-2 text-xs text-ink-faint">加载执行历史…</p>;
  }
  if (error) {
    return <p className="mt-2 text-xs text-red-600">{error}</p>;
  }
  if (runs.length === 0) {
    return <p className="mt-2 text-xs text-ink-faint">暂无执行记录</p>;
  }

  return (
    <ul className="mt-2 space-y-1.5 rounded-lg border border-line-soft bg-surface-subtle/60 px-3 py-2">
      {runs.map((run) => (
        <li key={run.id} className="flex flex-wrap items-start justify-between gap-2 text-xs">
          <span
            className={
              run.status === "success"
                ? "rounded-full bg-emerald-50 px-2 py-0.5 font-medium text-emerald-700"
                : "rounded-full bg-red-50 px-2 py-0.5 font-medium text-red-700"
            }
          >
            {run.status === "success" ? "成功" : "失败"}
          </span>
          <span className="tabular-nums text-ink-muted">{formatScheduleTime(run.started_at)}</span>
          {run.error_message ? <p className="w-full text-[11px] text-red-700 line-clamp-2">{run.error_message}</p> : null}
        </li>
      ))}
    </ul>
  );
}

export function AgentScheduleListItem({
  schedule,
  agentId,
  onEdit,
  onToggle,
  onDelete,
}: {
  schedule: AgentSchedule;
  agentId: string;
  onEdit: () => void;
  onToggle: () => void;
  onDelete: () => void;
}) {
  const [showRuns, setShowRuns] = useState(false);

  return (
    <article
      className={`rounded-xl border border-line bg-surface px-4 py-3 shadow-card transition hover:border-brand/25 ${schedule.enabled ? "" : "opacity-75"}`}
    >
      <div className="flex items-start gap-3">
        <div
          className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
            schedule.enabled ? "bg-brand-light text-brand" : "bg-surface-muted text-ink-faint"
          }`}
          aria-hidden
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" d="M12 7v5l3 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${
                schedule.enabled ? "bg-emerald-50 text-emerald-700" : "bg-surface-muted text-ink-faint"
              }`}
            >
              {schedule.enabled ? "启用" : "停用"}
            </span>
            <p className="min-w-0 flex-1 text-sm font-medium leading-snug text-ink line-clamp-2">{schedule.content.trim() || "（空内容）"}</p>
          </div>

          <p className="mt-1.5 text-xs font-medium text-brand">{schedule.cron_description}</p>
          <p className="mt-0.5 font-mono text-[11px] text-ink-faint">{schedule.cron}</p>

          <dl className="mt-2.5 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] text-ink-muted sm:grid-cols-2">
            <div>
              <dt className="text-ink-faint">下次执行</dt>
              <dd className="tabular-nums text-ink">{formatScheduleTime(schedule.next_run_at)}</dd>
            </div>
            <div>
              <dt className="text-ink-faint">上次执行</dt>
              <dd className="tabular-nums text-ink">{formatScheduleTime(schedule.last_run_at)}</dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line-soft pt-3">
        <button type="button" className="text-xs font-medium text-brand hover:underline" onClick={onEdit}>
          编辑
        </button>
        <button type="button" className="text-xs text-ink-muted hover:text-ink" onClick={() => setShowRuns((v) => !v)}>
          {showRuns ? "收起历史" : "执行历史"}
        </button>
        <button type="button" className="text-xs text-ink-muted hover:text-ink" onClick={onToggle}>
          {schedule.enabled ? "停用" : "启用"}
        </button>
        <button type="button" className="text-xs text-red-600 hover:underline" onClick={onDelete}>
          删除
        </button>
      </div>
      {showRuns ? <AgentScheduleRunsPanel agentId={agentId} scheduleId={schedule.id} /> : null}
    </article>
  );
}

export function AgentScheduleEmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 px-6 py-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-light text-brand">
        <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
          <path strokeLinecap="round" d="M12 7v5l3 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <div className="max-w-xs">
        <p className="text-sm font-medium text-ink">暂无定时任务</p>
        <p className="mt-1.5 text-xs leading-relaxed text-ink-faint">按 Cron 计划自动向当前智能体发送消息，触发后走合规、钩子与完整对话编排。</p>
      </div>
      <button type="button" className="btn-sm-primary" onClick={onCreate}>
        创建第一条任务
      </button>
    </div>
  );
}
