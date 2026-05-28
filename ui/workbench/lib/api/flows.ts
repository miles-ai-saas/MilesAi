import type { Flow, FlowGraph, FlowVersion } from "../types";
import type { ApiResponse } from "../types";
import { get, getPage, post, put, patch, http, unwrap, postWithTrace } from "./client";
import { appendTagIds } from "./query";
import { buildPageQuery, DEFAULT_PAGE_SIZE } from "../pagination";

export const flowsApi = {
  listFlows: (page = 1, size = DEFAULT_PAGE_SIZE, tagIds?: string[]) => {
    let q = buildPageQuery(page, size);
    q = appendTagIds(q, tagIds);
    return getPage<Flow>(`/flows?${q}`);
  },

  createFlow: (payload: { name: string; description?: string | null; tag_ids?: string[]; graph_json?: FlowGraph }) =>
    post<Flow>("/flows", {
      name: payload.name,
      description: payload.description ?? null,
      tag_ids: payload.tag_ids ?? [],
      graph_json: payload.graph_json ?? { nodes: [], edges: [] },
    }),

  updateFlow: (flowId: string, payload: { name?: string; description?: string | null; tag_ids?: string[] }) => patch<Flow>(`/flows/${flowId}`, payload),

  getFlow: (flowId: string) => get<Flow>(`/flows/${flowId}`),

  getFlowGraph: (flowId: string) => get<FlowVersion>(`/flows/${flowId}/graph`),

  listFlowVersions: (flowId: string) => get<import("../types").FlowVersionSummary[]>(`/flows/${flowId}/versions`),

  getFlowVersion: (flowId: string, version: number) => get<FlowVersion>(`/flows/${flowId}/versions/${version}`),

  saveFlowGraph: (flowId: string, graph_json: FlowGraph, remark?: string) => put<FlowVersion>(`/flows/${flowId}/graph`, { graph_json, remark }),

  publishFlow: (flowId: string) => post<Flow>(`/flows/${flowId}/publish`),

  deleteFlow: (flowId: string) => http.delete(`/flows/${flowId}`).then(() => undefined),

  compileFlow: (flowId: string) =>
    post<{
      compilable: boolean;
      engine: string;
      node_order: string[];
      node_types: string[];
      execution_layers: string[][];
      parallel_groups: string[][];
      conditional_nodes: string[];
      errors: string[];
      error_details: { code: string; message: string; node_id?: string | null }[];
    }>(`/flows/${flowId}/compile`),

  runFlow: (
    flowId: string,
    payload: {
      inputs: Record<string, string>;
      kb_ids?: string[];
      media?: import("../types").ChatMediaIn[];
    },
  ) =>
    post<{ output: unknown; steps: unknown[] }>(`/flows/${flowId}/run`, {
      inputs: payload.inputs,
      kb_ids: payload.kb_ids ?? [],
      ...(payload.media?.length ? { media: payload.media } : {}),
    }),
};
