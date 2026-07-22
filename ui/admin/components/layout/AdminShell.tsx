"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AdminSidebar, ADMIN_SIDEBAR_STORAGE_KEY } from "@/components/layout/AdminSidebar";
import { AdminTopBar } from "@/components/layout/AdminTopBar";
import { getAdminBreadcrumbs } from "@/lib/admin-nav";
import { adminApi } from "@/lib/api";
import { useAdminAuthStore, useAdminHydrated } from "@/lib/auth-store";

function loadSidebarCollapsed(): boolean {
  try {
    return localStorage.getItem(ADMIN_SIDEBAR_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function saveSidebarCollapsed(collapsed: boolean) {
  try {
    localStorage.setItem(ADMIN_SIDEBAR_STORAGE_KEY, collapsed ? "1" : "0");
  } catch {
    /* ignore */
  }
}

export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const hydrated = useAdminHydrated();
  const token = useAdminAuthStore((s) => s.accessToken);
  const admin = useAdminAuthStore((s) => s.admin);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    setSidebarCollapsed(loadSidebarCollapsed());
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    if (pathname === "/login" || pathname === "/login/") return;
    if (!token) window.location.href = "/login";
  }, [hydrated, token, pathname]);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  const toggleSidebarCollapsed = useCallback(() => {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      saveSidebarCollapsed(next);
      return next;
    });
  }, []);

  if (pathname === "/login" || pathname === "/login/") return <>{children}</>;

  if (!hydrated || !token) {
    return <p className="flex min-h-screen items-center justify-center text-ink-muted">加载中…</p>;
  }

  const breadcrumbs = getAdminBreadcrumbs(pathname);

  const logout = async () => {
    await adminApi.logout();
    window.location.href = "/login";
  };

  return (
    <div className="flex min-h-screen bg-surface-muted">
      <div className="relative z-30 hidden shrink-0 overflow-visible lg:block">
        <AdminSidebar
          pathname={pathname}
          collapsed={sidebarCollapsed}
          onToggleCollapse={toggleSidebarCollapsed}
        />
      </div>

      {mobileNavOpen && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <button type="button" className="absolute inset-0 bg-black/40" aria-label="关闭菜单" onClick={() => setMobileNavOpen(false)} />
          <div className="relative z-50 flex h-full shadow-panel">
            <AdminSidebar pathname={pathname} hideCollapseButton onNavigate={() => setMobileNavOpen(false)} />
          </div>
        </div>
      )}

      <div className="relative z-0 flex min-h-screen min-w-0 flex-1 flex-col">
        <AdminTopBar breadcrumbs={breadcrumbs} username={admin?.username} role={admin?.role} onMenuOpen={() => setMobileNavOpen(true)} onLogout={logout} />
        <main className="min-h-0 flex-1 overflow-auto">
          <div className="admin-page-shell">{children}</div>
        </main>
      </div>
    </div>
  );
}
