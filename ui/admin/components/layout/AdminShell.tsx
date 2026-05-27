"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AdminSidebar } from "@/components/layout/AdminSidebar";
import { AdminTopBar } from "@/components/layout/AdminTopBar";
import { getAdminBreadcrumbs } from "@/lib/admin-nav";
import { useAdminAuthStore, useAdminHydrated } from "@/lib/auth-store";

export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const hydrated = useAdminHydrated();
  const token = useAdminAuthStore((s) => s.accessToken);
  const admin = useAdminAuthStore((s) => s.admin);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    if (!hydrated) return;
    if (pathname === "/login") return;
    if (!token) router.replace("/login");
  }, [hydrated, token, pathname, router]);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  if (pathname === "/login") return <>{children}</>;

  if (!hydrated || !token) {
    return (
      <p className="flex min-h-screen items-center justify-center text-ink-muted">加载中…</p>
    );
  }

  const breadcrumbs = getAdminBreadcrumbs(pathname);

  const logout = () => {
    useAdminAuthStore.getState().logout();
    router.push("/login");
  };

  return (
    <div className="flex min-h-screen bg-surface-muted">
      <div className="hidden lg:flex lg:shrink-0">
        <AdminSidebar pathname={pathname} />
      </div>

      {mobileNavOpen && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/40"
            aria-label="关闭菜单"
            onClick={() => setMobileNavOpen(false)}
          />
          <div className="relative z-50 flex h-full shadow-panel">
            <AdminSidebar pathname={pathname} onNavigate={() => setMobileNavOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        <AdminTopBar
          breadcrumbs={breadcrumbs}
          username={admin?.username}
          role={admin?.role}
          onMenuOpen={() => setMobileNavOpen(true)}
          onLogout={logout}
        />
        <main className="min-h-0 flex-1 overflow-auto">
          <div className="admin-page-shell">{children}</div>
        </main>
      </div>
    </div>
  );
}
