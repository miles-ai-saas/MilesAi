"use client";

import { MCP_TRANSPORT_HINTS, McpTransportBadge } from "@/features/mcp/components/mcp-dialog-shared";
import type { McpTransportTab } from "@/features/mcp/lib/mcp-labels";
import { mcpTransportLabel } from "@/features/mcp/lib/mcp-labels";
import type { McpMeta } from "@/lib/types";

type TransportTab = {
  key: Exclude<McpTransportTab, "">;
  label: string;
  hint: string;
};

type Props = {
  transport: Exclude<McpTransportTab, "">;
  transportLocked: boolean;
  mcpMeta?: McpMeta | null;
  onTransportChange?: (t: Exclude<McpTransportTab, "">) => void;
};

export function McpServiceDialogTransport({ transport, transportLocked, mcpMeta, onTransportChange }: Props) {
  const tabs: TransportTab[] = (["http", "sse", "stdio"] as const).map((key) => ({
    key,
    label: mcpTransportLabel(key, mcpMeta),
    hint: MCP_TRANSPORT_HINTS[key],
  }));

  if (transportLocked) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-xs text-ink-muted">传输类型</span>
        <McpTransportBadge transport={transport} mcpMeta={mcpMeta} />
      </div>
    );
  }

  return (
    <div className="inline-flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1">
      {tabs.map((tab) => {
        const active = transport === tab.key;
        return (
          <button
            key={tab.key}
            type="button"
            title={tab.hint}
            onClick={() => onTransportChange?.(tab.key)}
            className={`rounded-lg px-4 py-2 text-left transition ${
              active ? "bg-brand-light text-brand shadow-sm ring-1 ring-brand/20" : "text-ink-muted hover:bg-surface-muted hover:text-ink"
            }`}
          >
            <span className="text-sm font-medium">{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}
