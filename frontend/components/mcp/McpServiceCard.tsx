"use client";

/** MCP 服务卡片（链路 §11 + mcp-labels）：协议/同步标签与底部操作。 */

import { CardActions } from "@/components/resource/CardActions";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import {
  formatMcpUpdatedAt,
  mcpCardDescription,
  mcpSyncStatusLabel,
  mcpTransportLabel,
  normalizeMcpTransport,
} from "@/lib/mcp-labels";
import type { McpMeta, McpService } from "@/lib/types";

const transportIcon: Record<"http" | "sse" | "stdio", string> = {
  http: "🌐",
  sse: "📡",
  stdio: "⌨️",
};

type Props = {
  service: McpService;
  mcpMeta?: McpMeta | null;
  onDetail: () => void;
  onSync: () => void;
  onEdit: () => void;
  onDelete: () => void;
};

export function McpServiceCard({
  service,
  mcpMeta,
  onDetail,
  onSync,
  onEdit,
  onDelete,
}: Props) {
  const transport = normalizeMcpTransport(service.transport);
  const sync = mcpSyncStatusLabel(service, mcpMeta);
  const toolCount = service.tools_cache?.length ?? 0;
  const warn = Boolean(service.sync_error) || sync.tone === "warn";

  const syncToneClass =
    sync.tone === "ok"
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : sync.tone === "warn"
        ? "border-amber-200 bg-amber-50 text-amber-800"
        : "border-line bg-surface-muted text-ink-muted";

  return (
    <ResourceItemCard
      title={
        <span className="inline-flex items-center gap-2">
          <span className="text-base leading-none" aria-hidden>
            {transportIcon[transport]}
          </span>
          <span className="line-clamp-1">{service.name}</span>
          {warn && (
            <span className="shrink-0 text-[10px] text-amber-500" title={service.sync_error ?? "未同步"}>
              ⚠
            </span>
          )}
        </span>
      }
      description={mcpCardDescription(service)}
      badge={mcpTransportLabel(service.transport, mcpMeta)}
      meta={
        <>
          <div className="flex flex-wrap gap-2">
            <span className={`rounded border px-2 py-0.5 text-[10px] font-medium ${syncToneClass}`}>
              {sync.label}
              {toolCount > 0 && sync.tone === "ok" ? ` · ${toolCount} 工具` : ""}
            </span>
          </div>
          {service.sync_error && (
            <p className="mt-2 text-amber-700 line-clamp-2" title={service.sync_error}>
              {service.sync_error}
            </p>
          )}
          <p className="mt-2">更新于 {formatMcpUpdatedAt(service) || "—"}</p>
        </>
      }
      actions={
        <CardActions
          actions={[
            { label: "详情", onClick: onDetail, variant: "primary" },
            { label: "同步工具", onClick: onSync },
            { label: "编辑", onClick: onEdit },
            { label: "删除", onClick: onDelete, variant: "danger" },
          ]}
        />
      }
    />
  );
}
