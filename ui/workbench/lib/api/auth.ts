import type { ApiResponse, TokenPair, UserInfo, TenantUser, PermissionGroup, Role, UserSession } from "../types";
import { useAuthStore } from "../auth-store";
import { get, getPage, post, put, patch, http, unwrap } from "./client";
import { buildPageQuery, DEFAULT_PAGE_SIZE } from "../pagination";

export const authApi = {
  login: async (username: string, password: string) => {
    const data = await post<TokenPair>("/auth/login", { username, password });
    useAuthStore.getState().setToken(data.access_token);
    const user = await get<UserInfo>("/auth/me");
    useAuthStore.getState().setUser(user);
    return { ...data, user };
  },

  fetchMe: () => get<UserInfo>("/auth/me"),

  logout: async () => {
    try {
      await http.post("/auth/logout");
    } catch {
      /* 本地仍清除会话 */
    }
    useAuthStore.getState().logout();
  },

  listMySessions: () => get<UserSession[]>("/auth/sessions"),

  revokeMySession: (jti: string) => http.delete(`/auth/sessions/${encodeURIComponent(jti)}`).then(() => undefined),

  revokeOtherSessions: () => post<{ revoked: number }>("/auth/sessions/revoke-others", {}),

  listUserSessions: (userId: string) => get<UserSession[]>(`/users/${userId}/sessions`),

  revokeAllUserSessions: (userId: string) => http.delete<ApiResponse<{ revoked: number }>>(`/users/${userId}/sessions`).then((r) => unwrap(r.data)),

  listUsers: (page = 1, size = DEFAULT_PAGE_SIZE) => getPage<TenantUser>(`/users?${buildPageQuery(page, size)}`),

  createUser: (payload: { username: string; email: string; password: string; phone?: string; role_ids?: string[] }) => post<TenantUser>("/users", payload),

  updateUser: (userId: string, payload: { email?: string; phone?: string; is_active?: boolean; role_ids?: string[] }) =>
    patch<TenantUser>(`/users/${userId}`, payload),

  resetUserPassword: (userId: string, password: string) => post<TenantUser>(`/users/${userId}/reset-password`, { password }),

  deactivateUser: (userId: string) => http.delete<ApiResponse<TenantUser>>(`/users/${userId}`).then((res) => unwrap(res.data)),

  batchDeactivateUsers: (userIds: string[]) =>
    post<{ deactivated: number; skipped: number }>("/users/batch-deactivate", {
      user_ids: userIds,
    }),

  batchUsers: (userIds: string[], action: "enable" | "disable" | "assign_roles" | "deactivate", roleIds?: string[]) =>
    post<{ processed: number; skipped: number; action: string; deactivated?: number }>("/users/batch", {
      user_ids: userIds,
      action,
      role_ids: roleIds,
    }),

  listPermissionGroups: () => get<PermissionGroup[]>("/roles/permissions"),

  listAssignableRoles: () => get<Role[]>("/roles/assignable"),

  listRoles: (page = 1, size = DEFAULT_PAGE_SIZE) => getPage<Role>(`/roles?${buildPageQuery(page, size)}`),

  createRole: (payload: { name: string; code: string; description?: string; permission_ids: string[] }) => post<Role>("/roles", payload),

  updateRole: (roleId: string, payload: { name?: string; description?: string; permission_ids?: string[] }) => patch<Role>(`/roles/${roleId}`, payload),

  deleteRole: (roleId: string) => http.delete(`/roles/${roleId}`).then(() => undefined),
};
