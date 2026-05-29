"use client";

import type { ReactNode } from "react";
import type { McpTransportTab } from "@/features/mcp/lib/mcp-labels";
import { mcpTransportLabel } from "@/features/mcp/lib/mcp-labels";
import type { McpMeta } from "@/lib/types";

export function McpDialogSection({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-line bg-surface-muted/30 p-4">
      <div className="mb-3">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{title}</h3>
        {hint ? <p className="mt-1 text-xs leading-relaxed text-ink-faint">{hint}</p> : null}
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

export function McpDetailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 border-b border-line-soft py-3 sm:grid-cols-[7rem_1fr]">
      <dt className="text-xs font-medium text-ink-muted">{label}</dt>
      <dd className="min-w-0 text-sm text-ink">{children}</dd>
    </div>
  );
}

export const MCP_TRANSPORT_HINTS: Record<Exclude<McpTransportTab, "">, string> = {
  http: "填写 Streamable HTTP 端点（如 https://host/mcp），平台优先 JSON，必要时回退 SSE。",
  sse: "填写 Legacy SSE 长连接 GET 地址（如 http://host/sse）；将接收 endpoint 事件并向消息 URL POST。",
  stdio: "经 MCP Runner 沙箱启动子进程；需管理员启用 Runner。npx 拉包需 network_mode=allow。",
};

export const MCP_ENDPOINT_PLACEHOLDER: Record<Exclude<McpTransportTab, "">, string> = {
  http: "https://example.com/mcp",
  sse: "http://127.0.0.1:3001/sse",
  stdio: "",
};

export function McpTransportBadge({ transport, mcpMeta }: { transport: Exclude<McpTransportTab, "">; mcpMeta?: McpMeta | null }) {
  return (
    <span className="inline-flex rounded border border-brand/20 bg-brand-light/30 px-2 py-0.5 text-[10px] font-medium text-brand">
      {mcpTransportLabel(transport, mcpMeta)}
    </span>
  );
}

export function mcpFormCanSubmit(opts: {
  name: string;
  transport: Exclude<McpTransportTab, "">;
  endpointUrl: string;
  stdioCommand: string;
  busy: boolean;
}): boolean {
  if (opts.busy || !opts.name.trim()) return false;
  if (opts.transport === "stdio") return Boolean(opts.stdioCommand.trim());
  return Boolean(opts.endpointUrl.trim());
}
