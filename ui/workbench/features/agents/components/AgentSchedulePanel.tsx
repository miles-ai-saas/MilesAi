"use client";

/** 智能体定时任务面板（链路 §10 cron-celery）。 */

import { AgentScheduleDialog } from "@/features/agents/components/AgentScheduleDialog";
import { AgentScheduleEmptyState, AgentScheduleListItem } from "@/features/agents/components/AgentScheduleListItem";
import { Pagination } from "@/components/ui/Pagination";
import { useAgentSchedulePanel } from "@/features/agents/hooks/use-agent-schedule-panel";

type Props = {
  agentId: string;
};

export function AgentSchedulePanel({ agentId }: Props) {
  const vm = useAgentSchedulePanel(agentId);

  if (vm.list.loading && vm.list.items.length === 0) {
    return <div className="flex flex-1 items-center justify-center p-6 text-sm text-ink-muted">加载中…</div>;
  }

  if (vm.list.error) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-sm">
        <p className="text-red-600">{vm.list.error}</p>
        <button type="button" className="btn-sm-outline" onClick={() => void vm.list.reload()}>
          重试
        </button>
      </div>
    );
  }

  const isEmpty = vm.list.items.length === 0;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-line-soft bg-surface-subtle/50 px-6 py-3">
        <div className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
          <span>
            共 <span className="font-medium tabular-nums text-ink">{vm.list.total}</span> 条
          </span>
          {!isEmpty && <span className="text-ink-faint">·</span>}
          {!isEmpty && (
            <span>
              本页 <span className="tabular-nums text-ink">{vm.enabledOnPage}</span> 条启用
            </span>
          )}
        </div>
        <button type="button" className="btn-sm-primary shrink-0" onClick={vm.openCreate}>
          新建任务
        </button>
      </div>

      {vm.msg && <p className="shrink-0 border-b border-line-soft bg-amber-50/80 px-6 py-2 text-xs text-amber-900">{vm.msg}</p>}

      <div className="min-h-0 flex-1 overflow-y-auto">
        {isEmpty ? (
          <AgentScheduleEmptyState onCreate={vm.openCreate} />
        ) : (
          <ul className="mx-auto max-w-3xl space-y-3 px-6 py-4">
            {vm.list.items.map((schedule) => (
              <li key={schedule.id}>
                <AgentScheduleListItem
                  schedule={schedule}
                  agentId={agentId}
                  onEdit={() => vm.openEdit(schedule)}
                  onToggle={() => void vm.onToggleEnabled(schedule)}
                  onDelete={() => vm.onDelete(schedule)}
                />
              </li>
            ))}
          </ul>
        )}
      </div>

      {!isEmpty && vm.list.total > 0 && (
        <div className="shrink-0 border-t border-line-soft bg-surface-subtle/40 px-6 py-2.5">
          <Pagination page={vm.list.page} size={vm.list.size} total={vm.list.total} onPageChange={vm.list.setPage} onSizeChange={vm.list.setSize} />
        </div>
      )}

      <AgentScheduleDialog
        open={vm.dialogOpen}
        agentId={agentId}
        schedule={vm.editing}
        onClose={() => vm.setDialogOpen(false)}
        onSaved={() => void vm.list.reload()}
      />
      {vm.confirmDialog}
    </div>
  );
}
