"use client";

/** MCP 添加入口卡片（链路 §11）。 */

import { AddResourceCard } from "@/components/resource/AddResourceCard";
import type { McpTransportTab } from "@/lib/mcp-labels";

type Props = {
  onAdd: (transport: Exclude<McpTransportTab, "">) => void;
};

export function McpCreateCard({ onAdd }: Props) {
  return (
    <AddResourceCard
      label="添加 MCP 服务"
      hint="支持 HTTP、SSE、STDIO；创建后同步 tools/list"
      onClick={() => onAdd("http")}
    />
  );
}
