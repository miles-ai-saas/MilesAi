"use client";

import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { StatChip } from "@/components/ui/StatChip";
import { invocationStatusLabel, toolSourceLabel } from "@/features/tools/lib/tool-labels";
import type { ToolsPageVm } from "@/features/tools/hooks/use-tools-page";
import type { ToolInvocationLog, ToolsMeta } from "@/lib/types";

function LogStatusBadge({ status, toolsMeta }: { status: string; toolsMeta: ToolsMeta | null }) {
  const failed = status === "failed" || status === "error";
  const ok = status === "success" || status === "ok";
  return (
    <span className={`badge ${ok ? "bg-emerald-50 text-emerald-800" : failed ? "bg-red-50 text-red-700" : "bg-surface-muted text-ink-muted"}`}>
      {invocationStatusLabel(status, toolsMeta)}
    </span>
  );
}

function InvocationLogRow({ log, toolsMeta }: { log: ToolInvocationLog; toolsMeta: ToolsMeta | null }) {
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

export function ToolsLogsTab({ vm }: { vm: ToolsPageVm }) {
  return (
    <ResourceListLayout
      {...vm.layoutCommon}
      searchPlaceholder="搜索工具编号、状态或错误信息"
      search={vm.search}
      onSearchChange={vm.setSearch}
      loading={vm.logList.loading}
      footer={
        !vm.logList.loading ? (
          <ResourceListFooter
            page={vm.logList.page}
            size={vm.logList.size}
            total={vm.logList.total}
            onPageChange={vm.logList.setPage}
            onSizeChange={vm.logList.setSize}
          />
        ) : null
      }
    >
      <div className="col-span-full grid gap-3 sm:grid-cols-2">
        <StatChip label="调用记录" value={String(vm.logList.total)} hint="当前租户审计日志总数" />
        <StatChip label="本页展示" value={String(vm.filteredLogs.length)} hint="受搜索筛选影响" />
      </div>
      <div className="col-span-full space-y-3">
        {!vm.logList.loading && vm.filteredLogs.length === 0 && (
          <p className="rounded-xl border border-dashed border-line py-12 text-center text-sm text-ink-faint">暂无调用记录</p>
        )}
        {vm.filteredLogs.map((log) => (
          <InvocationLogRow key={log.id} log={log} toolsMeta={vm.toolsMeta} />
        ))}
      </div>
    </ResourceListLayout>
  );
}
