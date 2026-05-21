"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { api } from "@/lib/api";
import { useAuthHydrated, useAuthStore } from "@/lib/auth-store";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { SectionLink } from "@/components/layout/SectionLink";
import { UserMenu } from "@/components/layout/UserMenu";
import { WorkbenchHeaderNav } from "@/components/layout/WorkbenchHeaderNav";
import { getAppSection, isFullBleedPage } from "@/lib/nav-config";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const hydrated = useAuthHydrated();
  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);

  const section = getAppSection(pathname);
  const isWorkbench = section === "workbench";
  const fullBleed = isFullBleedPage(pathname);

  useEffect(() => {
    if (!hydrated || !token || user) return;
    api.fetchMe().then(setUser).catch(() => {});
  }, [hydrated, token, user, setUser]);

  if (pathname === "/login") {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-screen flex-col bg-surface-muted">
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-surface px-4">
        <Link href="/workbench/dashboard" className="shrink-0 text-lg font-bold tracking-tight text-brand">
          AiEngine
        </Link>

        {isWorkbench ? (
          <WorkbenchHeaderNav pathname={pathname} />
        ) : (
          <div className="min-w-0 flex-1" />
        )}

        <div className="flex shrink-0 items-center gap-3 border-l border-line-soft pl-3">
          <SectionLink section={section} />
          <UserMenu variant="header" />
        </div>
      </header>

      {isWorkbench ? (
        <main className={`min-h-0 flex-1 overflow-auto ${fullBleed ? "" : "p-5 lg:px-8"}`}>
          {children}
        </main>
      ) : (
        <div className="flex min-h-0 flex-1">
          <AppSidebar pathname={pathname} />
          <main className="min-w-0 flex-1 overflow-auto p-5">{children}</main>
        </div>
      )}
    </div>
  );
}
