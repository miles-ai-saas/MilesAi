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
