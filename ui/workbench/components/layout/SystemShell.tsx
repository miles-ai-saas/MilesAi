"use client";

/** 系统管理区布局（链路 §7）：左侧 `SystemSidebar` + 顶栏面包屑（`nav-config`）。 */

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { SystemSidebar, SYSTEM_SIDEBAR_STORAGE_KEY } from "@/components/layout/SystemSidebar";
import { SystemTopBar } from "@/components/layout/SystemTopBar";
import { getSystemBreadcrumbs } from "@/lib/nav-config";

function loadSidebarCollapsed(): boolean {
  try {
    return localStorage.getItem(SYSTEM_SIDEBAR_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function saveSidebarCollapsed(collapsed: boolean) {
  try {
    localStorage.setItem(SYSTEM_SIDEBAR_STORAGE_KEY, collapsed ? "1" : "0");
  } catch {
    /* ignore */
  }
}

export function SystemShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const breadcrumbs = getSystemBreadcrumbs(pathname);

  useEffect(() => {
    setSidebarCollapsed(loadSidebarCollapsed());
  }, []);

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

  return (
    <div className="flex min-h-screen bg-surface-muted">
      <div className="relative z-30 hidden shrink-0 overflow-visible lg:block">
        <SystemSidebar
          pathname={pathname}
          collapsed={sidebarCollapsed}
          onToggleCollapse={toggleSidebarCollapsed}
        />
      </div>

      {mobileNavOpen && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <button type="button" className="absolute inset-0 bg-black/40" aria-label="关闭菜单" onClick={() => setMobileNavOpen(false)} />
          <div className="relative z-50 flex h-full shadow-panel">
            <SystemSidebar pathname={pathname} hideCollapseButton onNavigate={() => setMobileNavOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <SystemTopBar breadcrumbs={breadcrumbs} onMenuOpen={() => setMobileNavOpen(true)} />
        <main className="min-h-0 flex-1 overflow-auto">
          <div className="system-page-shell">{children}</div>
        </main>
      </div>
    </div>
  );
}
