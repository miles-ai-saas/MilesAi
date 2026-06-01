"use client";

/** 业务中心区布局（参考 SystemShell）：左侧 `BusinessSidebar` + 顶栏面包屑。 */

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { BusinessSidebar, BIZ_SIDEBAR_STORAGE_KEY } from "@/components/layout/BusinessSidebar";
import { BizTopBar } from "@/components/layout/BizTopBar";
import { getBusinessBreadcrumbs } from "@/lib/nav-config";

function loadSidebarCollapsed(): boolean {
  try {
    return localStorage.getItem(BIZ_SIDEBAR_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function saveSidebarCollapsed(collapsed: boolean) {
  try {
    localStorage.setItem(BIZ_SIDEBAR_STORAGE_KEY, collapsed ? "1" : "0");
  } catch {
    /* ignore */
  }
}

export function BusinessShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const breadcrumbs = getBusinessBreadcrumbs(pathname);

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
    <div className="flex h-dvh overflow-hidden bg-surface-muted">
      <div className="relative z-30 hidden h-full shrink-0 overflow-visible lg:block">
        <BusinessSidebar
          pathname={pathname}
          collapsed={sidebarCollapsed}
          onToggleCollapse={toggleSidebarCollapsed}
        />
      </div>

      {mobileNavOpen && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <button type="button" className="absolute inset-0 bg-black/40" aria-label="关闭菜单" onClick={() => setMobileNavOpen(false)} />
          <div className="relative z-50 flex h-full shadow-panel">
            <BusinessSidebar pathname={pathname} hideCollapseButton onNavigate={() => setMobileNavOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <BizTopBar breadcrumbs={breadcrumbs} onMenuOpen={() => setMobileNavOpen(true)} />
        <main className="min-h-0 flex-1 overflow-y-auto bg-surface-muted">
          <div className="system-page-shell min-h-full">{children}</div>
        </main>
      </div>
    </div>
  );
}
