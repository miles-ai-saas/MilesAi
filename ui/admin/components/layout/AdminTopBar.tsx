"use client";

import type { BreadcrumbItem } from "@/lib/admin-nav";
import { AdminBreadcrumb } from "@/components/layout/AdminBreadcrumb";
import { AdminUserMenu } from "@/components/layout/AdminUserMenu";

export function AdminTopBar({
  breadcrumbs,
  username,
  role,
  onMenuOpen,
  onLogout,
}: {
  breadcrumbs: BreadcrumbItem[];
  username?: string;
  role?: string;
  onMenuOpen: () => void;
  onLogout: () => void;
}) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-line bg-surface px-4 lg:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-line text-ink-muted transition hover:bg-surface-muted lg:hidden"
          onClick={onMenuOpen}
          aria-label="打开菜单"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <AdminBreadcrumb items={breadcrumbs} />
      </div>

      <AdminUserMenu username={username} role={role} onLogout={onLogout} />
    </header>
  );
}
