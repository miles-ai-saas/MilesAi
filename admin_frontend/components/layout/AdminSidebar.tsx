"use client";

import Link from "next/link";
import {
  ADMIN_ACCOUNT_NAV,
  ADMIN_NAV,
  isAdminNavActive,
  type AdminNavItem,
} from "@/lib/admin-nav";
import { AdminNavIcon } from "@/components/layout/AdminNavIcon";

function NavLink({
  item,
  pathname,
  onNavigate,
}: {
  item: AdminNavItem;
  pathname: string;
  onNavigate?: () => void;
}) {
  const active = isAdminNavActive(pathname, item.href);
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      className={`admin-nav-item ${active ? "admin-nav-item-active" : ""}`}
    >
      <AdminNavIcon icon={item.icon} className="h-[18px] w-[18px] shrink-0" />
      <span className="truncate">{item.label}</span>
    </Link>
  );
}

export function AdminSidebar({
  pathname,
  username,
  role,
  onNavigate,
}: {
  pathname: string;
  username?: string;
  role?: string;
  onNavigate?: () => void;
}) {
  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-line bg-surface">
      <div className="flex h-14 shrink-0 items-center gap-2.5 border-b border-line px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-light text-sm font-bold text-brand">
          A
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-brand">MilesAi</p>
          <p className="truncate text-[11px] text-ink-faint">平台管理后台</p>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {ADMIN_NAV.map((group) => (
          <div key={group.title} className="mb-5 last:mb-0">
            <p className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
              {group.title}
            </p>
            <ul className="space-y-0.5">
              {group.items.map((item) => (
                <li key={item.href}>
                  <NavLink item={item} pathname={pathname} onNavigate={onNavigate} />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <div className="shrink-0 border-t border-line bg-surface-subtle p-3">
        <NavLink item={ADMIN_ACCOUNT_NAV} pathname={pathname} onNavigate={onNavigate} />
        {username && (
          <div className="mt-3 rounded-lg border border-line bg-brand-light/60 px-3 py-2.5">
            <p className="truncate text-sm font-medium text-ink">{username}</p>
            {role && <p className="truncate text-xs text-ink-muted">{role}</p>}
          </div>
        )}
      </div>
    </aside>
  );
}
