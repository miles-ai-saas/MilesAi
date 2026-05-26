"use client";

/** MCP 服务详情（链路 §11）：连接信息、同步状态与 tools/list 缓存。 */

import { McpDetailRow, McpDialogSection, McpTransportBadge } from "@/components/mcp/mcp-dialog-shared";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { KbPageAlert } from "@/components/kb/KbPageAlert";
import {
  formatMcpUpdatedAt,
  mcpCardDescription,
  mcpStatusLabel,
  mcpSyncStatusLabel,
  mcpTransportLabel,
  normalizeMcpTransport,
} from "@/lib/mcp-labels";
import type { McpMeta, McpService } from "@/lib/types";

type Props = {
  open: boolean;
  service: McpService | null;
  mcpMeta?: McpMeta | null;
  syncing?: boolean;
  onClose: () => void;
  onSync?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
};

function ToolsTable({ tools }: { tools: Record<string, unknown>[] }) {
  if (tools.length === 0) {
    return <p className="text-sm text-ink-muted">暂无工具，请点击「同步工具」拉取 tools/list。</p>;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-line">
      <table className="w-full min-w-[24rem] text-left text-xs">
        <thead className="bg-surface-muted/60 text-ink-muted">
          <tr>
            <th className="px-3 py-2 font-medium">工具名</th>
            <th className="px-3 py-2 font-medium">说明</th>
          </tr>
        </thead>
        <tbody>
          {tools.map((t, i) => (
            <tr key={`${String(t.name)}-${i}`} className="border-t border-line-soft">
              <td className="px-3 py-2 font-mono text-ink">{String(t.name ?? "—")}</td>
              <td className="px-3 py-2 text-ink-muted">{String(t.description ?? "—")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ConnectionBlock({ service }: { service: McpService }) {
  const transport = normalizeMcpTransport(service.transport);

  if (transport === "stdio") {
    const cmd = String(service.connection_config?.command ?? "");
    const args = (service.connection_config?.args as string[] | undefined) ?? [];
    return (
      <>
        <McpDetailRow label="启动命令">
          <span className="font-mono text-xs break-all">{cmd || "—"}</span>
        </McpDetailRow>
        <McpDetailRow label="参数">
          {args.length === 0 ? (
            <span className="text-ink-muted">无</span>
          ) : (
            <pre className="overflow-x-auto rounded-lg border border-line bg-surface-muted/40 p-2 font-mono text-xs">
              {args.join("\n")}
            </pre>
          )}
        </McpDetailRow>
      </>
    );
  }

  const url =
    service.endpoint_url.startsWith("stdio://") ? "—" : service.endpoint_url;

  return (
    <McpDetailRow label="端点 URL">
      <span className="break-all font-mono text-xs">{url}</span>
    </McpDetailRow>
  );
}

export function McpServiceDetailDialog({
  open,
  service,
  mcpMeta,
  syncing,
  onClose,
  onSync,
  onEdit,
  onDelete,
}: Props) {
  if (!service) return null;

  const transport = normalizeMcpTransport(service.transport);
  const sync = mcpSyncStatusLabel(service, mcpMeta);
  const tools = service.tools_cache ?? [];
  const updated = formatMcpUpdatedAt(service);

  const syncToneClass =
    sync.tone === "ok"
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : sync.tone === "warn"
        ? "border-amber-200 bg-amber-50 text-amber-800"
        : "border-line bg-surface-muted text-ink-muted";

  return (
    <ResourceDialog
      open={open}
      size="sheet"
      contentMaxWidth="max-w-4xl"
      title={service.name}
      description={mcpCardDescription(service)}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={onClose}>
            关闭
          </button>
          {onDelete && (
            <button type="button" className="btn-ghost text-red-600" onClick={onDelete}>
              删除
            </button>
          )}
          {onEdit && (
            <button type="button" className="btn-ghost border border-line" onClick={onEdit}>
              编辑
            </button>
          )}
          {onSync && (
            <button type="button" className="btn-primary" disabled={syncing} onClick={onSync}>
              {syncing ? "同步中…" : "同步工具"}
            </button>
          )}
        </>
      }
    >
      <div className="space-y-5">
        {service.sync_error ? (
          <KbPageAlert tone="error" message={service.sync_error} />
        ) : null}

        <McpDialogSection title="概览">
          <dl>
            <McpDetailRow label="传输类型">
              <McpTransportBadge transport={transport} mcpMeta={mcpMeta} />
            </McpDetailRow>
            <McpDetailRow label="运行状态">{mcpStatusLabel(service.status, mcpMeta)}</McpDetailRow>
            <McpDetailRow label="同步状态">
              <span
                className={`inline-flex rounded border px-2 py-0.5 text-[10px] font-medium ${syncToneClass}`}
              >
                {sync.label}
                {tools.length > 0 && sync.tone === "ok" ? ` · ${tools.length} 工具` : ""}
              </span>
            </McpDetailRow>
            {updated && <McpDetailRow label="最近更新">{updated}</McpDetailRow>}
            <McpDetailRow label="描述">
              {service.description?.trim() ? (
                <p className="whitespace-pre-wrap leading-relaxed">{service.description}</p>
              ) : (
                <span className="text-ink-muted">—</span>
              )}
            </McpDetailRow>
          </dl>
        </McpDialogSection>

        <McpDialogSection
          title="连接配置"
          hint={mcpTransportLabel(transport, mcpMeta)}
        >
          <dl>
            <ConnectionBlock service={service} />
          </dl>
        </McpDialogSection>

        <McpDialogSection title="已同步工具" hint="来自最近一次 tools/list">
          <ToolsTable tools={tools} />
        </McpDialogSection>
      </div>
    </ResourceDialog>
  );
}
