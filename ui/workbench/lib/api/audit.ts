import type { TenantAuditLog } from "../types";
import type { ApiResponse } from "../types";
import { get, getPage, post, put, patch, http, unwrap, postWithTrace } from "./client";
import { appendTagIds } from "./query";
import { buildPageQuery, DEFAULT_PAGE_SIZE } from "../pagination";

export const auditApi = {
  listAuditLogs: (
    page = 1,
    size = DEFAULT_PAGE_SIZE,
    filters?: { action?: string; resource_type?: string },
  ) => {
    const q = new URLSearchParams(buildPageQuery(page, size));
    if (filters?.action) q.set("action", filters.action);
    if (filters?.resource_type) q.set("resource_type", filters.resource_type);
    return getPage<TenantAuditLog>(`/audit/logs?${q.toString()}`);
  },

};
