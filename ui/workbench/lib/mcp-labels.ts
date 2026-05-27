/**
 * MCP 工作台展示文案：优先 `GET /mcp/meta`（`useMcpMeta`），未加载时本地 fallback。
 * 链路见 `lib/enum-meta.ts`、`docs/guides/hooks.md` §9。；链路 §4 见 lib/chains.ts。
 */

import { optionLabel, type EnumOption } from "@/lib/enum-meta";
import type { McpMeta, McpService } from "@/lib/types";

export type McpTransportTab = "" | "http" | "sse" | "stdio";

const TRANSPORT_FILTER_FALLBACK: EnumOption[] = [
  { value: "", label: "全部" },
  { value: "http", label: "HTTP" },
  { value: "sse", label: "SSE" },
  { value: "stdio", label: "STDIO" },
];

const TRANSPORT_TYPE_FALLBACK: Record<string, string> = {
  http: "HTTP",
  sse: "SSE",
  stdio: "STDIO",
};

const SYNC_DISPLAY_FALLBACK: Record<string, string> = {
  synced: "已同步",
  unsynced: "未同步",
  sync_failed: "同步失败",
};

export function mcpTransportFilterOptions(meta?: McpMeta | null): EnumOption[] {
  return meta?.transport_filters?.length ? meta.transport_filters : TRANSPORT_FILTER_FALLBACK;
}

/** 与后端 McpTransport 对齐。 */
export function normalizeMcpTransport(transport?: string | null): "http" | "sse" | "stdio" {
  const t = (transport || "sse").toLowerCase();
  if (t === "http") return "http";
  if (t === "stdio") return "stdio";
  return "sse";
}

export function mcpTransportLabel(
  transport?: string | null,
  meta?: McpMeta | null,
): string {
  const key = normalizeMcpTransport(transport);
  return optionLabel(meta?.transport_types, key) || TRANSPORT_TYPE_FALLBACK[key] || key;
}

function mcpSyncDisplayKey(s: McpService): "sync_failed" | "synced" | "unsynced" {
  if (s.sync_error) return "sync_failed";
  if (s.last_sync_at && (s.tools_cache?.length ?? 0) > 0) return "synced";
  return "unsynced";
}

export function mcpSyncStatusLabel(
  s: McpService,
  meta?: McpMeta | null,
): { label: string; tone: "ok" | "warn" | "muted" } {
  const key = mcpSyncDisplayKey(s);
  const label =
    optionLabel(meta?.sync_displays, key) || SYNC_DISPLAY_FALLBACK[key] || key;
  if (key === "sync_failed") return { label, tone: "warn" };
  if (key === "synced") return { label, tone: "ok" };
  return { label, tone: "muted" };
}

export function mcpStatusLabel(status: string, meta?: McpMeta | null): string {
  return optionLabel(meta?.statuses, status) || status;
}

export function formatMcpUpdatedAt(s: McpService): string {
  const raw = s.last_sync_at || s.updated_at || s.created_at;
  if (!raw) return "";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** 卡片副标题：优先 description，STDIO 展示 command+args。 */
export function mcpCardDescription(s: McpService): string {
  if (s.description?.trim()) return s.description.trim();
  const t = normalizeMcpTransport(s.transport);
  if (t === "stdio") {
    const cmd = String(s.connection_config?.command ?? "");
    const args = (s.connection_config?.args as string[] | undefined) ?? [];
    return [cmd, ...args].filter(Boolean).join(" ") || s.endpoint_url;
  }
  return s.endpoint_url;
}
