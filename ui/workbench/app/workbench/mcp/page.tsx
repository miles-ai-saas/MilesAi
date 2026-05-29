"use client";

/**
 * MCP 服务管理页（链路 §11，见 lib/chains.ts）：传输类型筛选、卡片列表、同步/编辑/删除。
 * SSE 类型 endpoint 应填 GET 长连接地址（如 /sse），由后端 legacy_sse 客户端处理。
 */

import { McpPageView, useMcpPage } from "@/features/mcp";

export default function McpPage() {
  const vm = useMcpPage();
  return <McpPageView vm={vm} />;
}
