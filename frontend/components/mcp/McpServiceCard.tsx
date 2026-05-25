"use client";

/** 已注册 MCP 服务卡片：协议标签、同步状态、··· 菜单与可展开工具列表。 */

import { CardOverflowMenu, type OverflowMenuItem } from "@/components/resource/CardOverflowMenu";
import {
  formatMcpUpdatedAt,
  mcpCardDescription,
  mcpSyncStatusLabel,
  mcpTransportLabel,
  normalizeMcpTransport,
} from "@/lib/mcp-labels";
import type { McpService } from "@/lib/types";

const transportIcon: Record<"http" | "sse" | "stdio", string> = {
  http: "🌐",
  sse: "📡",
  stdio: "⌨️",
};

type Props = {
  service: McpService;
  onSync: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onToggleTools: () => void;
  toolsExpanded: boolean;
};

export function McpServiceCard({
  service,
  onSync,
  onEdit,
  onDelete,
  onToggleTools,
  toolsExpanded,
}: Props) {
  const transport = normalizeMcpTransport(service.transport);
  const sync = mcpSyncStatusLabel(service);
  const toolCount = service.tools_cache?.length ?? 0;
  const warn = Boolean(service.sync_error) || sync.tone === "warn";

  const menuItems: OverflowMenuItem[] = [
    { label: "同步工具", onClick: onSync },
    { label: toolsExpanded ? "收起工具" : "工具列表", onClick: onToggleTools },
    { label: "编辑", onClick: onEdit },
    { label: "删除", onClick: onDelete, variant: "danger" },
  ];

  const syncToneClass =
    sync.tone === "ok"
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : sync.tone === "warn"
        ? "border-amber-200 bg-amber-50 text-amber-800"
        : "border-line bg-surface-muted text-ink-muted";

  return (
    <article className="resource-card relative !min-h-[176px]">
      <div className="flex items-start gap-3">
        <span className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-surface-muted text-lg">
          {transportIcon[transport]}
          {warn && (
            <span
              className="absolute -right-0.5 -top-0.5 text-[10px] text-amber-500"
              title={service.sync_error ?? "未同步"}
            >
              ⚠
            </span>
          )}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <h3 className="min-w-0 flex-1 font-medium text-ink line-clamp-1">{service.name}</h3>
            <CardOverflowMenu
              items={menuItems}
              label={`${service.name} 更多操作`}
              trigger="dots"
            />
          </div>
          <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-ink-muted">
            {mcpCardDescription(service)}
          </p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <span className="rounded border border-brand/20 bg-brand-light/30 px-2 py-0.5 text-[10px] font-medium text-brand">
          {mcpTransportLabel(service.transport)}
        </span>
        <span className={`rounded border px-2 py-0.5 text-[10px] font-medium ${syncToneClass}`}>
          {sync.label}
          {toolCount > 0 && sync.tone === "ok" ? ` · ${toolCount} 工具` : ""}
        </span>
      </div>

      {service.sync_error && (
        <p className="mt-2 text-xs text-amber-700 line-clamp-2" title={service.sync_error}>
          {service.sync_error}
        </p>
      )}

      <p className="mt-auto pt-3 text-xs text-ink-faint">
        更新于 {formatMcpUpdatedAt(service) || "—"}
      </p>

      {toolsExpanded && (
        <ul className="mt-3 max-h-28 space-y-1 overflow-y-auto border-t border-line-soft pt-3 text-xs text-ink-muted">
          {(service.tools_cache ?? []).length === 0 ? (
            <li>暂无工具，请先同步</li>
          ) : (
            (service.tools_cache ?? []).map((t, i) => (
              <li key={i}>
                <span className="font-medium text-ink">{String(t.name)}</span>
                {t.description ? ` — ${String(t.description)}` : ""}
              </li>
            ))
          )}
        </ul>
      )}
    </article>
  );
}
