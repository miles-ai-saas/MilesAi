import type { ApiResponse } from "../types";
import { get, getPage, post, put, patch, http, unwrap, postWithTrace } from "./client";
import { appendTagIds } from "./query";
import { buildPageQuery, DEFAULT_PAGE_SIZE } from "../pagination";

export const toolsApi = {
  listToolCatalog: (source?: string, categoryId?: string, tagIds?: string[]) => {
    const q = new URLSearchParams();
    if (source) q.set("source", source);
    if (categoryId) q.set("category_id", categoryId);
    tagIds?.forEach((id) => q.append("tag_ids", id));
    const qs = q.toString();
    return get<import("../types").ToolCatalogItem[]>(`/tools/catalog${qs ? `?${qs}` : ""}`);
  },

  listCustomTools: (page = 1, size = DEFAULT_PAGE_SIZE, categoryId?: string, tagIds?: string[]) => {
    let qs = buildPageQuery(page, size);
    if (categoryId) qs += `&category_id=${categoryId}`;
    qs = appendTagIds(qs, tagIds);
    return getPage<import("../types").CustomTool>(`/tools?${qs}`);
  },

  getCustomTool: (id: string) => get<import("../types").CustomTool>(`/tools/${id}`),

  createCustomTool: (payload: import("../types").ToolCreatePayload) =>
    post<import("../types").CustomTool>("/tools", { tool_type: "http", ...payload }),

  updateCustomTool: (id: string, payload: Partial<import("../types").ToolCreatePayload & { is_active?: boolean }>) =>
    patch<import("../types").CustomTool>(`/tools/${id}`, payload),

  deleteCustomTool: (id: string) => http.delete(`/tools/${id}`).then(() => undefined),

  invokeTool: (
    name: string,
    params: Record<string, unknown>,
    toolId?: string,
    confirmed = false,
  ) =>
    post<{
      tool: string;
      source: string;
      status: string;
      output: Record<string, unknown>;
      pending?: import("../types").PendingToolCall | null;
    }>(`/tools/${encodeURIComponent(name)}/invoke`, {
      params,
      tool_id: toolId || null,
      confirmed,
    }),

  listToolInvocationLogs: (page = 1, size = DEFAULT_PAGE_SIZE, toolSlug?: string) => {
    const q = new URLSearchParams(buildPageQuery(page, size));
    if (toolSlug) q.set("tool_slug", toolSlug);
    return getPage<import("../types").ToolInvocationLog>(`/tools/invocation-logs?${q.toString()}`);
  },

  listBuiltinTools: () => get<Record<string, string>[]>("/tools/builtin"),

  // --- 技能包（SKILL.md 落盘，见 docs/guides/skill-packages.md）---
};
