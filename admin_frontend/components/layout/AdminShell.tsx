"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAdminAuthStore, useAdminHydrated } from "@/lib/auth-store";

const NAV = [
  { href: "/", label: "概览" },
  { href: "/tenants", label: "租户管理" },
  { href: "/billing", label: "计费管理" },
  { href: "/risk", label: "风控管理" },
  { href: "/audit", label: "审计日志" },
  { href: "/profile", label: "账号安全" },
];

const TENANT_WEB_URL = process.env.NEXT_PUBLIC_TENANT_WEB_URL || "http://localhost:3000";

export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const hydrated = useAdminHydrated();
  const token = useAdminAuthStore((s) => s.accessToken);
  const admin = useAdminAuthStore((s) => s.admin);

  useEffect(() => {
    if (!hydrated) return;
    if (pathname === "/login") return;
    if (!token) router.replace("/login");
  }, [hydrated, token, pathname, router]);

  if (pathname === "/login") return <>{children}</>;

  if (!hydrated || !token) {
    return (
      <p className="flex min-h-screen items-center justify-center text-ink-muted">加载中…</p>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-surface-muted">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-line bg-surface px-4 lg:px-6">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-lg font-bold tracking-tight text-brand">
            AiEngine
          </Link>
          <span className="hidden text-sm text-ink-faint sm:inline">平台运营后台</span>
        </div>
        <div className="flex items-center gap-4">
          {admin && (
            <p className="hidden text-sm text-ink-muted sm:block">
              <span className="font-medium text-ink">{admin.username}</span>
              <span className="text-ink-faint"> · {admin.role}</span>
            </p>
          )}
          <a
            href={TENANT_WEB_URL}
            target="_blank"
            rel="noreferrer"
            className="text-sm text-ink-muted transition hover:text-brand"
          >
            租户工作台 ↗
          </a>
          <button
            type="button"
            className="text-sm text-ink-muted transition hover:text-brand-dark"
            onClick={() => {
              useAdminAuthStore.getState().logout();
              router.push("/login");
            }}
          >
            退出
          </button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <aside className="flex w-52 shrink-0 flex-col border-r border-line bg-surface">
          <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-4">
            <p className="mb-1.5 px-3 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
              运营管理
            </p>
            {NAV.map((item) => {
              const active =
                item.href === "/"
                  ? pathname === "/"
                  : pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`nav-item ${active ? "nav-item-active" : "hover:bg-surface-muted"}`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </aside>

        <main className="min-w-0 flex-1 overflow-auto p-5 lg:p-6">{children}</main>
      </div>
    </div>
  );
}
