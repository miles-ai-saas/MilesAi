import axios from "axios";
import type { ApiResponse, PageResult } from "./types";
import { getAdminToken, useAdminAuthStore } from "./auth-store";
import { getApiErrorMessage } from "./api-error";

export { getApiErrorMessage } from "./api-error";

const baseURL =
  process.env.NEXT_PUBLIC_ADMIN_API_URL || "http://localhost:8000/api/admin/v1";

const http = axios.create({ baseURL, timeout: 120000 });

http.interceptors.request.use((config) => {
  const token = getAdminToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

http.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && typeof window !== "undefined") {
      if (getAdminToken()) {
        useAdminAuthStore.getState().logout();
        window.location.href = "/login";
      }
    }
    return Promise.reject(new Error(getApiErrorMessage(err)));
  },
);

function unwrap<T>(body: ApiResponse<T>): T {
  if (body.code !== 0) {
    throw new Error(body.message || "请求失败");
  }
  return body.data as T;
}

async function get<T>(url: string) {
  return unwrap((await http.get<ApiResponse<T>>(url)).data);
}

async function post<T>(url: string, data?: unknown) {
  return unwrap((await http.post<ApiResponse<T>>(url, data)).data);
}

async function patch<T>(url: string, data?: unknown) {
  return unwrap((await http.patch<ApiResponse<T>>(url, data)).data);
}

async function del<T>(url: string) {
  return unwrap((await http.delete<ApiResponse<T>>(url)).data);
}

export const adminApi = {
  login: async (username: string, password: string) => {
    const data = await post<{ access_token: string }>("/auth/login", { username, password });
    useAdminAuthStore.getState().setToken(data.access_token);
    const me = await get<{ id: string; username: string; role: string }>("/auth/me");
    useAdminAuthStore.getState().setAdmin(me);
    return data;
  },
  logout: async () => {
    try {
      await post<null>("/auth/logout", {});
    } catch {
      /* 令牌已失效时仍清本地状态 */
    }
    useAdminAuthStore.getState().logout();
  },
  me: () => get<{ id: string; username: string; role: string }>("/auth/me"),
  changePassword: (old_password: string, new_password: string) =>
    post<null>("/auth/change-password", { old_password, new_password }),
  listSessions: () =>
    get<{ admin_id: string; username: string; role: string; is_current: boolean }[]>(
      "/auth/sessions",
    ),
  revokeSession: (adminId: string) => del<null>(`/auth/sessions/${adminId}`),

  listAdmins: (page = 1, size = 50) =>
    get<PageResult<PlatformAdmin>>(`/admins?page=${page}&size=${size}`),
  createAdmin: (body: {
    username: string;
    password: string;
    email?: string;
    display_name?: string;
    role?: string;
  }) => post<PlatformAdmin>("/admins", body),
  updateAdmin: (id: string, body: Record<string, unknown>) =>
    patch<PlatformAdmin>(`/admins/${id}`, body),
  disableAdmin: (id: string) => del<null>(`/admins/${id}`),
  resetAdminPassword: (id: string, new_password: string) =>
    post<null>(`/admins/${id}/reset-password`, { new_password }),

  getDashboardSummary: () =>
    get<{
      tenants_total: number;
      tenants_active: number;
      risk_open: number;
      bills_total: number;
      bills_issued_month: number;
      audit_today: number;
      plans_active: number;
    }>("/dashboard/summary"),

  listTenants: (page = 1, size = 50, status?: string) =>
    get<PageResult<AdminTenant>>(
      `/tenants?page=${page}&size=${size}${status ? `&status=${status}` : ""}`,
    ),
  getTenant: (id: string) => get<AdminTenantDetail>(`/tenants/${id}`),
  getTenantUsage: (id: string) =>
    get<AdminTenantDetail["usage"]>(`/tenants/${id}/usage`),
  createTenant: (body: Record<string, unknown>) => post<AdminTenant>("/tenants", body),
  updateTenant: (id: string, body: Record<string, unknown>) =>
    patch<AdminTenant>(`/tenants/${id}`, body),
  updateQuota: (id: string, body: Record<string, unknown>) =>
    patch<AdminTenant>(`/tenants/${id}/quota`, body),
  deleteTenant: (id: string) => del<null>(`/tenants/${id}`),

  listPlans: () => get<BillingPlan[]>("/billing/plans"),
  createPlan: (body: Record<string, unknown>) => post<BillingPlan>("/billing/plans", body),
  updatePlan: (id: string, body: Record<string, unknown>) =>
    patch<BillingPlan>(`/billing/plans/${id}`, body),
  listBills: (tenantId?: string) =>
    get<PageResult<TenantBill>>(
      `/billing/bills?page=1&size=50${tenantId ? `&tenant_id=${tenantId}` : ""}`,
    ),
  getBill: (id: string) => get<TenantBillDetail>(`/billing/bills/${id}`),
  generateBill: (tenantId: string, period_start: string, period_end: string) =>
    post<TenantBillDetail>(
      `/billing/bills/generate?tenant_id=${tenantId}&period_start=${period_start}&period_end=${period_end}`,
    ),
  updateBillStatus: (id: string, status: "paid" | "void") =>
    patch<TenantBillDetail>(`/billing/bills/${id}`, { status }),

  listRiskEvents: () => get<PageResult<RiskEvent>>("/risk/events?page=1&size=50"),
  resolveRisk: (id: string) => post<RiskEvent>(`/risk/events/${id}/resolve`),
  listIpBlacklist: () => get<IpBlacklist[]>("/risk/ip-blacklist"),
  addIp: (ip_address: string, reason?: string) =>
    post<IpBlacklist>("/risk/ip-blacklist", { ip_address, reason }),
  toggleIp: (id: string, is_active: boolean) =>
    patch<IpBlacklist>(`/risk/ip-blacklist/${id}?is_active=${is_active}`),
  listRateLimits: () => get<RateLimitRule[]>("/risk/rate-limits"),
  createRateLimit: (body: Record<string, unknown>) => post<RateLimitRule>("/risk/rate-limits", body),
  listAuditLogs: (opts?: { action?: string; tenant_id?: string; page?: number; size?: number }) => {
    const q = new URLSearchParams({
      page: String(opts?.page ?? 1),
      size: String(opts?.size ?? 100),
    });
    if (opts?.action) q.set("action", opts.action);
    if (opts?.tenant_id) q.set("tenant_id", opts.tenant_id);
    return get<PageResult<AuditLog>>(`/audit/logs?${q.toString()}`);
  },
  exportAuditLogs: async (opts?: { action?: string; tenant_id?: string }) => {
    const q = new URLSearchParams();
    if (opts?.action) q.set("action", opts.action);
    if (opts?.tenant_id) q.set("tenant_id", opts.tenant_id);
    const suffix = q.toString() ? `?${q.toString()}` : "";
    const token = getAdminToken();
    const res = await fetch(`${baseURL}/audit/logs/export${suffix}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error("导出失败");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "admin-audit-logs.csv";
    a.click();
    URL.revokeObjectURL(url);
  },

  listModelCatalog: (vendor?: string, publish_status?: string) => {
    const q = new URLSearchParams({ page: "1", size: "100" });
    if (vendor) q.set("vendor", vendor);
    if (publish_status) q.set("publish_status", publish_status);
    return get<PageResult<AdminModelCatalog>>("/model-catalog?" + q.toString());
  },
  createModelCatalog: (body: Record<string, unknown>) =>
    post<AdminModelCatalog>("/model-catalog", body),
  updateModelCatalog: (id: string, body: Record<string, unknown>) =>
    patch<AdminModelCatalog>(`/model-catalog/${id}`, body),
  publishModelCatalog: (id: string) => post<AdminModelCatalog>(`/model-catalog/${id}/publish`),
  deprecateModelCatalog: (id: string) =>
    post<AdminModelCatalog>(`/model-catalog/${id}/deprecate`),
  deleteModelCatalog: (id: string) =>
    http.delete(`/model-catalog/${id}`).then(() => undefined),

  listMarketplaceCategories: () => get<AdminMarketplaceCategory[]>("/marketplace-categories"),
  createMarketplaceCategory: (body: {
    name: string;
    slug?: string;
    sort_order?: number;
  }) => post<AdminMarketplaceCategory>("/marketplace-categories", body),
  updateMarketplaceCategory: (
    id: string,
    body: { name?: string; slug?: string; sort_order?: number },
  ) => patch<AdminMarketplaceCategory>(`/marketplace-categories/${id}`, body),
  deleteMarketplaceCategory: (id: string) =>
    http.delete(`/marketplace-categories/${id}`).then(() => undefined),

  listSysCategories: (domain: string) =>
    get<AdminSysCategory[]>(`/sys-categories?domain=${encodeURIComponent(domain)}`),
  createSysCategory: (
    domain: string,
    body: { name: string; slug?: string; sort_order?: number },
  ) =>
    post<AdminSysCategory>(`/sys-categories?domain=${encodeURIComponent(domain)}`, body),
  updateSysCategory: (
    id: string,
    body: { name?: string; slug?: string; sort_order?: number },
  ) => patch<AdminSysCategory>(`/sys-categories/${id}`, body),
  deleteSysCategory: (id: string) => http.delete(`/sys-categories/${id}`).then(() => undefined),

  getMarketplaceReviewMode: () => get<{ review_mode: string }>("/marketplace/review-mode"),
  listPendingMarketplaceApps: (page = 1, size = 50) =>
    get<PageResult<AdminMarketplaceApp>>(`/marketplace/apps/pending?page=${page}&size=${size}`),
  getMarketplaceAppForReview: (id: string) =>
    get<AdminMarketplaceAppDetail>(`/marketplace/apps/${id}`),
  approveMarketplaceApp: (id: string) => post<AdminMarketplaceApp>(`/marketplace/apps/${id}/approve`),
  rejectMarketplaceApp: (id: string, note?: string) =>
    post<AdminMarketplaceApp>(`/marketplace/apps/${id}/reject`, { note }),
};

export interface PlatformAdmin {
  id: string;
  username: string;
  email?: string | null;
  display_name?: string | null;
  role: string;
  is_active: boolean;
}

export interface AdminMarketplaceApp {
  id: string;
  name: string;
  description?: string | null;
  icon?: string | null;
  version: string;
  status: string;
  category_name?: string | null;
  submitted_at?: string | null;
  review_note?: string | null;
}

export interface AdminMarketplaceAppDetail extends AdminMarketplaceApp {
  manifest: Record<string, unknown>;
}

export interface AdminSysCategory {
  id: string;
  domain: string;
  name: string;
  slug: string;
  sort_order: number;
  is_system: boolean;
  created_at: string;
  updated_at?: string | null;
}

export interface AdminMarketplaceCategory {
  id: string;
  name: string;
  slug: string;
  sort_order: number;
  app_count: number;
}

export interface AdminModelCatalog {
  id: string;
  name: string;
  vendor: string;
  provider: string;
  model_name: string;
  model_code: string | null;
  model_type: string;
  description: string | null;
  context_window: string | null;
  badge: string | null;
  publish_status: string;
  is_active: boolean;
  is_featured: boolean;
  has_api_key: boolean;
  api_base: string | null;
  sort_order: number;
}

export interface AdminTenant {
  id: string;
  name: string;
  description?: string | null;
  is_active: boolean;
  status: string;
  plan_id?: string | null;
  plan_name?: string | null;
  max_knowledge_bases: number;
  max_storage_mb: number;
  max_tokens_monthly: number;
  max_agents: number;
  max_flows: number;
  tokens_used_month: number;
  storage_used_mb: number;
  created_at: string;
}

export interface AdminTenantDetail extends AdminTenant {
  usage: {
    knowledge_bases: number;
    documents: number;
    agents: number;
    flows: number;
    users: number;
    storage_used_mb: number;
    tokens_used_month: number;
  };
}

export interface BillingPlan {
  id: string;
  code: string;
  name: string;
  price_monthly: string;
  max_tokens_monthly: number;
  max_storage_mb: number;
  is_active: boolean;
}

export interface TenantBill {
  id: string;
  tenant_id: string;
  tenant_name?: string;
  amount: string;
  status: string;
  period_start: string;
  period_end: string;
  tokens_used: number;
  storage_used_mb: number;
}

export interface TenantBillDetail extends TenantBill {
  line_items: { item_type: string; description?: string; amount: string; quantity: string }[];
}

export interface RiskEvent {
  id: string;
  event_type: string;
  severity: string;
  ip_address?: string;
  is_resolved: boolean;
  created_at: string;
}

export interface IpBlacklist {
  id: string;
  ip_address: string;
  reason?: string;
  is_active: boolean;
}

export interface RateLimitRule {
  id: string;
  name: string;
  path_pattern: string;
  limit_per_minute: number;
  is_active: boolean;
}

export interface AuditLog {
  id: string;
  action: string;
  tenant_id?: string;
  ip_address?: string;
  created_at: string;
  detail: Record<string, unknown>;
}
