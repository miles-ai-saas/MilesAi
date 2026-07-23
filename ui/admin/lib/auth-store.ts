import { useEffect, useState } from "react";
import { create } from "zustand";
import { persist } from "zustand/middleware";

const STORAGE_KEY = "milesai-admin-auth";

interface AdminAuthState {
  accessToken: string | null;
  admin: { id: string; username: string; role: string } | null;
  setToken: (token: string | null) => void;
  setAdmin: (admin: AdminAuthState["admin"]) => void;
  logout: () => void;
}

export const useAdminAuthStore = create<AdminAuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      admin: null,
      setToken: (token) => set({ accessToken: token }),
      setAdmin: (admin) => set({ admin }),
      logout: () => set({ accessToken: null, admin: null }),
    }),
    { name: STORAGE_KEY },
  ),
);

export function getAdminToken(): string | null {
  const fromStore = useAdminAuthStore.getState().accessToken;
  if (fromStore) return fromStore;
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw)?.state?.accessToken ?? null;
  } catch {
    return null;
  }
}

/** 去掉尾斜杠，兼容 trailingSlash + OSS 静态托管。 */
export function normalizePath(path: string): string {
  if (!path) return "/";
  const trimmed = path.replace(/\/+$/, "");
  return trimmed === "" ? "/" : trimmed;
}

export function isLoginPath(path: string): boolean {
  return normalizePath(path) === "/login";
}

/**
 * 静态导出 + trailingSlash 下必须跳 `/login/`。
 * 若已在登录页则不再跳转，避免 `/login` ↔ `/login/` 死循环。
 */
export function redirectToLogin(query = ""): void {
  if (typeof window === "undefined") return;
  if (isLoginPath(window.location.pathname)) return;
  const qs = query.startsWith("?") ? query : query ? `?${query}` : "";
  window.location.replace(`/login/${qs}`);
}

export function redirectToHome(): void {
  if (typeof window === "undefined") return;
  window.location.replace("/");
}

export function useAdminHydrated(): boolean {
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => {
    if (useAdminAuthStore.persist.hasHydrated()) {
      setHydrated(true);
      return;
    }
    return useAdminAuthStore.persist.onFinishHydration(() => setHydrated(true));
  }, []);
  return hydrated;
}

export function useRequireAdmin(): boolean {
  const hydrated = useAdminHydrated();
  const token = useAdminAuthStore((s) => s.accessToken);
  return hydrated && !!token;
}
