/** MCP 工作台：传输类型 Tab、卡片文案与同步状态展示。 */

import type { McpService } from "@/lib/types";

export type McpTransportTab = "" | "http" | "sse" | "stdio";

export const MCP_TRANSPORT_TABS: { key: McpTransportTab; label: string }[] = [
  { key: "", label: "全部" },
  { key: "http", label: "HTTP" },
  { key: "sse", label: "SSE" },
  { key: "stdio", label: "STDIO" },
];

/** 与后端 normalize_transport 对齐（含 streamable-http → http）。 */
export function normalizeMcpTransport(transport?: string | null): "http" | "sse" | "stdio" {
  const t = (transport || "sse").toLowerCase();
  if (t === "http" || t === "streamable-http") return "http";
  if (t === "stdio") return "stdio";
  return "sse";
}

export function mcpTransportLabel(transport?: string | null): string {
  const map = { http: "HTTP", sse: "SSE", stdio: "STDIO" } as const;
  return map[normalizeMcpTransport(transport)];
}

export function mcpSyncStatusLabel(s: McpService): { label: string; tone: "ok" | "warn" | "muted" } {
  if (s.sync_error) return { label: "同步失败", tone: "warn" };
  if (s.last_sync_at && (s.tools_cache?.length ?? 0) > 0) {
    return { label: "已同步", tone: "ok" };
  }
  return { label: "未同步", tone: "muted" };
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
