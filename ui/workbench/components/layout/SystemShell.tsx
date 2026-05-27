"use client";

/** 系统管理区布局（链路 §7）：左侧 `SystemSidebar` + 顶栏面包屑（`nav-config`）。 */

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { SystemSidebar } from "@/components/layout/SystemSidebar";
import { SystemTopBar } from "@/components/layout/SystemTopBar";
import { getSystemBreadcrumbs } from "@/lib/nav-config";

export function SystemShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const breadcrumbs = getSystemBreadcrumbs(pathname);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  return (
    <div className="flex min-h-screen bg-surface-muted">
      <div className="hidden lg:flex lg:shrink-0">
        <SystemSidebar pathname={pathname} />
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
            <SystemSidebar
              pathname={pathname}
              onNavigate={() => setMobileNavOpen(false)}
            />
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
