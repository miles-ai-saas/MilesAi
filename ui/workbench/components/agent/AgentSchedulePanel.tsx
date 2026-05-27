"use client";

/** 智能体定时任务面板（链路 §10 cron-celery）。 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { AgentScheduleDialog } from "@/components/agent/AgentScheduleDialog";
import { Pagination } from "@/components/ui/Pagination";
import { api } from "@/lib/api";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { needsPagination } from "@/lib/pagination";
import type { AgentSchedule, AgentScheduleRun } from "@/lib/types";

type Props = {
  agentId: string;
};

function formatTime(iso?: string | null): string {
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

function ScheduleRunsPanel({ agentId, scheduleId }: { agentId: string; scheduleId: string }) {
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
          <span className="tabular-nums text-ink-muted">{formatTime(run.started_at)}</span>
          {run.error_message ? (
            <p className="w-full text-[11px] text-red-700 line-clamp-2">{run.error_message}</p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function ScheduleListItem({
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
      className={`rounded-xl border border-line bg-surface px-4 py-3 shadow-card transition hover:border-brand/25 ${
        schedule.enabled ? "" : "opacity-75"
      }`}
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
                schedule.enabled
                  ? "bg-emerald-50 text-emerald-700"
                  : "bg-surface-muted text-ink-faint"
              }`}
            >
              {schedule.enabled ? "启用" : "停用"}
            </span>
            <p className="min-w-0 flex-1 text-sm font-medium leading-snug text-ink line-clamp-2">
              {schedule.content.trim() || "（空内容）"}
            </p>
          </div>

          <p className="mt-1.5 text-xs font-medium text-brand">{schedule.cron_description}</p>
          <p className="mt-0.5 font-mono text-[11px] text-ink-faint">{schedule.cron}</p>

          <dl className="mt-2.5 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] text-ink-muted sm:grid-cols-2">
            <div>
              <dt className="text-ink-faint">下次执行</dt>
              <dd className="tabular-nums text-ink">{formatTime(schedule.next_run_at)}</dd>
            </div>
            <div>
              <dt className="text-ink-faint">上次执行</dt>
              <dd className="tabular-nums text-ink">{formatTime(schedule.last_run_at)}</dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line-soft pt-3">
        <button type="button" className="text-xs font-medium text-brand hover:underline" onClick={onEdit}>
          编辑
        </button>
        <button
          type="button"
          className="text-xs text-ink-muted hover:text-ink"
          onClick={() => setShowRuns((v) => !v)}
        >
          {showRuns ? "收起历史" : "执行历史"}
        </button>
        <button
          type="button"
          className="text-xs text-ink-muted hover:text-ink"
          onClick={onToggle}
        >
          {schedule.enabled ? "停用" : "启用"}
        </button>
        <button type="button" className="text-xs text-red-600 hover:underline" onClick={onDelete}>
          删除
        </button>
      </div>
      {showRuns ? <ScheduleRunsPanel agentId={agentId} scheduleId={schedule.id} /> : null}
    </article>
  );
}

export function AgentSchedulePanel({ agentId }: Props) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<AgentSchedule | null>(null);
  const [msg, setMsg] = useState("");

  const list = usePagedList(
    useCallback((page, size) => api.listAgentSchedules(agentId, page, size), [agentId]),
    { resetKey: agentId },
  );
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const enabledOnPage = useMemo(
    () => list.items.filter((s) => s.enabled).length,
    [list.items],
  );

  const openCreate = () => {
    setEditing(null);
    setDialogOpen(true);
  };

  const openEdit = (schedule: AgentSchedule) => {
    setEditing(schedule);
    setDialogOpen(true);
  };

  const onToggleEnabled = async (schedule: AgentSchedule) => {
    setMsg("");
    try {
      await api.updateAgentSchedule(agentId, schedule.id, { enabled: !schedule.enabled });
      await list.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "更新失败");
    }
  };

  const onDelete = (schedule: AgentSchedule) => {
    const preview =
      schedule.content.trim().length > 80
        ? `${schedule.content.trim().slice(0, 80)}…`
        : schedule.content.trim();
    requestConfirm({
      title: "删除定时任务",
      message: (
        <>
          确定删除该定时任务？
          {preview && <span className="mt-1 block text-ink-muted">{preview}</span>}
        </>
      ),
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deleteAgentSchedule(agentId, schedule.id);
        await list.reload();
      },
    });
  };

  if (list.loading && list.items.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-sm text-ink-muted">加载中…</div>
    );
  }

  if (list.error) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-sm">
        <p className="text-red-600">{list.error}</p>
        <button type="button" className="btn-sm-outline" onClick={() => void list.reload()}>
          重试
        </button>
      </div>
    );
  }

  const isEmpty = list.items.length === 0;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-line-soft bg-surface-subtle/50 px-6 py-3">
        <div className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
          <span>
            共 <span className="font-medium tabular-nums text-ink">{list.total}</span> 条
          </span>
          {!isEmpty && (
            <span className="text-ink-faint">·</span>
          )}
          {!isEmpty && (
            <span>
              本页 <span className="tabular-nums text-ink">{enabledOnPage}</span> 条启用
            </span>
          )}
        </div>
        <button type="button" className="btn-sm-primary shrink-0" onClick={openCreate}>
          新建任务
        </button>
      </div>

      {msg && (
        <p className="shrink-0 border-b border-line-soft bg-amber-50/80 px-6 py-2 text-xs text-amber-900">
          {msg}
        </p>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto">
        {isEmpty ? (
          <div className="flex flex-col items-center justify-center gap-4 px-6 py-16 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-light text-brand">
              <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                <path strokeLinecap="round" d="M12 7v5l3 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div className="max-w-xs">
              <p className="text-sm font-medium text-ink">暂无定时任务</p>
              <p className="mt-1.5 text-xs leading-relaxed text-ink-faint">
                按 Cron 计划自动向当前智能体发送消息，触发后走合规、钩子与完整对话编排。
              </p>
            </div>
            <button type="button" className="btn-sm-primary" onClick={openCreate}>
              创建第一条任务
            </button>
          </div>
        ) : (
          <ul className="mx-auto max-w-3xl space-y-3 px-6 py-4">
            {list.items.map((schedule) => (
              <li key={schedule.id}>
                <ScheduleListItem
                  schedule={schedule}
                  agentId={agentId}
                  onEdit={() => openEdit(schedule)}
                  onToggle={() => void onToggleEnabled(schedule)}
                  onDelete={() => onDelete(schedule)}
                />
              </li>
            ))}
          </ul>
        )}
      </div>

      {!isEmpty && (
        <div className="shrink-0 border-t border-line-soft bg-surface-subtle/40 px-6 py-2.5">
          {needsPagination(list.total, list.size) ? (
            <Pagination
              page={list.page}
              size={list.size}
              total={list.total}
              onPageChange={list.setPage}
            />
          ) : (
            <p className="text-center text-[11px] text-ink-faint">已加载全部 {list.total} 条</p>
          )}
        </div>
      )}

      <AgentScheduleDialog
        open={dialogOpen}
        agentId={agentId}
        schedule={editing}
        onClose={() => setDialogOpen(false)}
        onSaved={() => void list.reload()}
      />
      {confirmDialog}
    </div>
  );
}
