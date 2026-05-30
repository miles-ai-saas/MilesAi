"use client";

import { FilterChip } from "@/components/ui/FilterChip";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { AgentCallRecordDetailDialog } from "@/features/agents/components/AgentCallRecordDetailDialog";
import {
  agentCallRouteLabel,
  agentCallStatusLabel,
  CALL_RECORD_STATUS_CHIPS,
  formatCallRecordTime,
  shortenTraceId,
} from "@/features/agents/lib/agent-call-record-labels";
import type { AgentCallRecordsPanelVm } from "@/features/agents/hooks/use-agent-call-records-panel";
import type { AgentCallRecord } from "@/lib/types";

function StatusBadge({ status }: { status: string }) {
  const ok = status === "success";
  const blocked = status === "blocked";
  return (
    <span
      className={`badge ${ok ? "bg-emerald-50 text-emerald-800" : blocked ? "bg-amber-50 text-amber-800" : "bg-red-50 text-red-700"}`}
    >
      {agentCallStatusLabel(status)}
    </span>
  );
}

type Props = {
  agentId: string;
  conversationId?: string;
  vm: AgentCallRecordsPanelVm;
  onOpenTrace?: () => void;
  onOpenTraceFromRecord?: (sessionId: string) => void | Promise<void>;
};

export function AgentCallRecordsPanel({ agentId, conversationId, vm, onOpenTrace, onOpenTraceFromRecord }: Props) {
  const { list, draft, setDraft, applyFilters, resetFilters, setStatusFilter, hasActiveFilters, selectedId, setSelectedId, filters } = vm;

  if (list.loading && list.items.length === 0) {
    return <div className="flex flex-1 items-center justify-center p-6 text-sm text-ink-muted">加载中…</div>;
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

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="shrink-0 space-y-3 border-b border-line-soft bg-surface-subtle/50 px-6 py-3">
        <div className="flex flex-wrap items-center gap-2">
          {CALL_RECORD_STATUS_CHIPS.map((chip) => (
            <FilterChip key={chip.value || "all"} active={filters.status === chip.value} label={chip.label} onClick={() => setStatusFilter(chip.value)} />
          ))}
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="min-w-[10rem] flex-[2]">
            <span className="mb-1 block text-xs text-ink-muted">会话 ID</span>
            <input
              className="input-field text-sm"
              value={draft.conversationId}
              placeholder={conversationId ? "当前会话" : "可选"}
              onChange={(e) => setDraft({ ...draft, conversationId: e.target.value })}
            />
          </label>
          <label className="min-w-[10rem] flex-[2]">
            <span className="mb-1 block text-xs text-ink-muted">搜索</span>
            <input
              className="input-field text-sm"
              value={draft.q}
              placeholder="问题摘要或 trace_id"
              onChange={(e) => setDraft({ ...draft, q: e.target.value })}
              onKeyDown={(e) => {
                if (e.key === "Enter") applyFilters();
              }}
            />
          </label>
          <div className="flex shrink-0 gap-2 pb-0.5">
            <button type="button" className="btn-sm-primary" onClick={applyFilters}>
              筛选
            </button>
            {hasActiveFilters && (
              <button type="button" className="btn-sm-outline" onClick={resetFilters}>
                重置
              </button>
            )}
          </div>
        </div>
        <p className="text-xs text-ink-muted">
          共 <span className="tabular-nums text-ink">{list.total}</span> 条调用记录
        </p>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[880px] text-left text-sm">
            <thead className="border-b border-line bg-surface-muted text-xs text-ink-muted">
              <tr>
                <th className="whitespace-nowrap px-4 py-2">时间</th>
                <th className="whitespace-nowrap px-4 py-2">状态</th>
                <th className="whitespace-nowrap px-4 py-2">路径</th>
                <th className="whitespace-nowrap px-4 py-2">用户</th>
                <th className="px-4 py-2">问题摘要</th>
                <th className="whitespace-nowrap px-4 py-2">耗时</th>
                <th className="whitespace-nowrap px-4 py-2">Token</th>
                <th className="whitespace-nowrap px-4 py-2">trace_id</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-soft">
              {list.items.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-ink-faint">
                    {hasActiveFilters ? "当前筛选条件下暂无调用记录" : "暂无调用记录，发送消息后将在此展示"}
                  </td>
                </tr>
              ) : (
                list.items.map((row: AgentCallRecord) => (
                  <tr
                    key={row.id}
                    className="cursor-pointer transition hover:bg-surface-muted/60"
                    onClick={() => setSelectedId(row.id)}
                  >
                    <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-ink-muted">{formatCallRecordTime(row.created_at)}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-ink-muted">{agentCallRouteLabel(row.route)}</td>
                    <td className="px-4 py-3 text-ink">{row.actor_username ?? "—"}</td>
                    <td className="max-w-[16rem] truncate px-4 py-3 text-ink" title={row.query_preview}>
                      {row.query_preview || "—"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 tabular-nums text-ink-muted">{row.latency_ms} ms</td>
                    <td className="whitespace-nowrap px-4 py-3 tabular-nums text-ink-muted">
                      {row.prompt_tokens + row.completion_tokens > 0 ? row.prompt_tokens + row.completion_tokens : "—"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-ink-faint" title={row.trace_id ?? undefined}>
                      {shortenTraceId(row.trace_id)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <ResourceListFooter
        className="shrink-0 border-t border-line-soft px-6 py-2.5"
        page={list.page}
        size={list.size}
        total={list.total}
        onPageChange={list.setPage}
        onSizeChange={list.setSize}
      />

      <AgentCallRecordDetailDialog
        agentId={agentId}
        callId={selectedId}
        onClose={() => setSelectedId(null)}
        conversationId={conversationId}
        onOpenTrace={onOpenTrace ? () => onOpenTrace() : undefined}
        onOpenTraceFromRecord={onOpenTraceFromRecord}
      />
    </div>
  );
}
