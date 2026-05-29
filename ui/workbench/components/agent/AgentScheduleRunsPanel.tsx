"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatScheduleTime } from "@/lib/agent-schedule-shared";
import type { AgentScheduleRun } from "@/lib/types";

export function AgentScheduleRunsPanel({ agentId, scheduleId }: { agentId: string; scheduleId: string }) {
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
