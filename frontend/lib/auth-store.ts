import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { UserInfo } from "./types";

const STORAGE_KEY = "milesai-auth";

interface AuthState {
  accessToken: string | null;
  user: UserInfo | null;
  setToken: (token: string | null) => void;
  setUser: (user: UserInfo | null) => void;
  setSession: (token: string, user: UserInfo) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      user: null,
      setToken: (token) => set({ accessToken: token }),
      setUser: (user) => set({ user }),
      setSession: (token, user) => set({ accessToken: token, user }),
      logout: () => set({ accessToken: null, user: null }),
    }),
    { name: STORAGE_KEY }
  )
);

/** 从内存或 localStorage 同步读取 token（避免 persist 水合前 token 为空） */
export function getAccessToken(): string | null {
  const fromStore = useAuthStore.getState().accessToken;
  if (fromStore) return fromStore;
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as {
      state?: { accessToken?: string | null };
    };
    return parsed.state?.accessToken ?? null;
  } catch {
    return null;
  }
}

/** zustand persist 从 localStorage 恢复完成前，内存里 token 仍为 null */
export function useAuthHydrated(): boolean {
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    if (useAuthStore.persist.hasHydrated()) {
      setHydrated(true);
      return;
    }
    return useAuthStore.persist.onFinishHydration(() => setHydrated(true));
  }, []);

  return hydrated;
}

/** 等水合后再判断登录；未登录则跳转 /login */
export function useRequireAuth(): { ready: boolean; token: string | null; user: UserInfo | null } {
  const hydrated = useAuthHydrated();
  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const router = useRouter();

  useEffect(() => {
    if (!hydrated) return;
    if (!token) router.replace("/login");
  }, [hydrated, token, router]);

  return { ready: hydrated && !!token, token: hydrated ? token : null, user };
}
