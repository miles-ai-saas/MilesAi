import type { McpService } from "../types";
import type { ApiResponse } from "../types";
import { get, getPage, post, put, patch, http, unwrap, postWithTrace } from "./client";
import { appendTagIds } from "./query";
import { buildPageQuery, DEFAULT_PAGE_SIZE } from "../pagination";

export const mcpApi = {
  listMcpServices: (page = 1, size = DEFAULT_PAGE_SIZE, transport?: string) => {
    const q = buildPageQuery(page, size);
    const extra = transport ? `&transport=${encodeURIComponent(transport)}` : "";
    return getPage<McpService>(`/mcp?${q}${extra}`);
  },

  createMcpService: (payload: { name: string; transport: string; endpoint_url?: string; description?: string; connection_config?: Record<string, unknown> }) =>
    post<McpService>("/mcp", payload),

  updateMcpService: (
    id: string,
    payload: {
      name?: string;
      transport?: string;
      endpoint_url?: string;
      description?: string;
      connection_config?: Record<string, unknown>;
    },
  ) => patch<McpService>(`/mcp/${id}`, payload),

  deleteMcpService: (id: string) => http.delete(`/mcp/${id}`).then(() => undefined),

  syncMcpService: (serviceId: string) => post<{ tools: Record<string, unknown>[]; synced_at: string }>(`/mcp/${serviceId}/sync`),

  invokeMcpTool: (serviceId: string, toolName: string, params: Record<string, unknown>) =>
    post<{ service_id: string; tool_name: string; output: Record<string, unknown> }>(`/mcp/${serviceId}/tools/${encodeURIComponent(toolName)}/invoke`, {
      params,
    }),
};
