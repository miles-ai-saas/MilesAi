"use client";

import { FilterChip } from "@/components/ui/FilterChip";
import { StatChip } from "@/components/ui/StatChip";
import { invocationStatusLabel, toolSourceLabel } from "@/lib/tool-labels";
import type { ToolInvocationLog, ToolsMeta } from "@/lib/types";

export { FilterChip, StatChip };

function LogStatusBadge({ status, toolsMeta }: { status: string; toolsMeta: ToolsMeta | null }) {
  const failed = status === "failed" || status === "error";
  const ok = status === "success" || status === "ok";
  return (
    <span className={`badge ${ok ? "bg-emerald-50 text-emerald-800" : failed ? "bg-red-50 text-red-700" : "bg-surface-muted text-ink-muted"}`}>
      {invocationStatusLabel(status, toolsMeta)}
    </span>
  );
}

export function InvocationLogRow({ log, toolsMeta }: { log: ToolInvocationLog; toolsMeta: ToolsMeta | null }) {
  return (
    <article className="rounded-xl border border-line bg-surface p-4 shadow-card transition hover:border-brand/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium text-ink">{log.tool_slug}</h3>
            <LogStatusBadge status={log.status} toolsMeta={toolsMeta} />
            <span className="badge bg-brand-light text-brand">{toolSourceLabel(log.source, toolsMeta)}</span>
            <span className="text-xs text-ink-muted">{log.invoke_source}</span>
          </div>
          <p className="mt-2 text-xs text-ink-muted">{log.latency_ms != null ? `耗时 ${log.latency_ms} ms` : "—"}</p>
        </div>
        <time className="shrink-0 font-mono text-xs text-ink-faint">{new Date(log.created_at).toLocaleString("zh-CN")}</time>
      </div>
      {log.error_message && (
        <p className="mt-3 rounded-lg bg-red-50/80 px-3 py-2 text-xs text-red-700 line-clamp-3">{log.error_message}</p>
      )}
    </article>
  );
}
