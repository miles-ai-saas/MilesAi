import type { HookDefinition, HookBinding } from "../types";
import type { ApiResponse } from "../types";
import { get, getPage, post, put, patch, http, unwrap, postWithTrace } from "./client";
import { appendTagIds } from "./query";
import { buildPageQuery, DEFAULT_PAGE_SIZE } from "../pagination";

export const hooksApi = {
  listHooks: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<HookDefinition>(`/hooks?${buildPageQuery(page, size)}`),

  createHook: (payload: {
    name: string;
    hook_type?: string;
    config: Record<string, unknown>;
    trigger?: string;
    scope?: string;
    target_id?: string;
    priority?: number;
  }) => post<HookDefinition>("/hooks", payload),

  updateHook: (
    id: string,
    payload: { name?: string; config?: Record<string, unknown>; is_active?: boolean },
  ) => patch<HookDefinition>(`/hooks/${id}`, payload),

  deleteHook: (id: string) => http.delete(`/hooks/${id}`).then(() => undefined),

  listHookBindings: (hookId: string) => get<HookBinding[]>(`/hooks/${hookId}/bindings`),

  createHookBinding: (
    hookId: string,
    payload: { scope?: string; target_id?: string; trigger?: string; priority?: number },
  ) => post<HookBinding>(`/hooks/${hookId}/bindings`, payload),

  deleteHookBinding: (bindingId: string) =>
    http.delete(`/hooks/bindings/${bindingId}`).then(() => undefined),

  listHookExecutions: (hookId: string, page = 1, size = 10) =>
    getPage<import("../types").HookExecutionLog>(
      `/hooks/executions?hook_id=${hookId}&${buildPageQuery(page, size)}`,
    ),

};
