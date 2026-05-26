"use client";

/**
 * 根布局壳层（链路 §7）：按路径选择工作台顶栏或 `SystemShell`；登录页无壳。
 * 鉴权补全见 §1：`fetchMe` 填充 user。
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { api } from "@/lib/api";
import { useAuthHydrated, useAuthStore } from "@/lib/auth-store";
import { BrandHeader } from "@/components/brand/brand-header";
import { SystemShell } from "@/components/layout/SystemShell";
import { SectionLink } from "@/components/layout/SectionLink";
import { UserMenu } from "@/components/layout/UserMenu";
import { WorkbenchHeaderNav } from "@/components/layout/WorkbenchHeaderNav";
import {
  getAppSection,
  isFullBleedPage,
  isFullHeightPage,
} from "@/lib/nav-config";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const hydrated = useAuthHydrated();
  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);

  const section = getAppSection(pathname);
  const isWorkbench = section === "workbench";
  const fullBleed = isFullBleedPage(pathname);
  const fullHeight = isFullHeightPage(pathname);

  useEffect(() => {
    if (!hydrated || !token || user) return;
    api.fetchMe().then(setUser).catch(() => {});
  }, [hydrated, token, user, setUser]);

  if (pathname === "/login") {
    return <>{children}</>;
  }

  if (section === "system") {
    return <SystemShell>{children}</SystemShell>;
  }

  return (
    <div
      className={`flex flex-col bg-surface-muted ${
        fullHeight ? "h-dvh overflow-hidden" : "min-h-screen"
      }`}
    >
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-surface px-4">
        <BrandHeader productLine="MilesAi · 工作台" href="/workbench/dashboard" />

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

      <main
        className={`min-h-0 flex-1 ${
          fullHeight
            ? "flex h-0 flex-col overflow-hidden"
            : "overflow-auto"
        } ${fullBleed ? "" : "p-4 lg:px-6"}`}
      >
        {children}
      </main>
    </div>
  );
}
