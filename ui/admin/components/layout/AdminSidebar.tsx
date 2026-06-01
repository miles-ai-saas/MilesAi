"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BrandHeader } from "@/components/brand/brand-header";
import { CompanyLogo } from "@/components/brand/company-logo";
import { ADMIN_NAV, isAdminNavActive, type AdminNavGroup, type AdminNavItem } from "@/lib/admin-nav";
import { AdminNavIcon } from "@/components/layout/AdminNavIcon";
import { adminApi } from "@/lib/api";
import { useAdminAuthStore } from "@/lib/auth-store";

export const ADMIN_SIDEBAR_EXPANDED = 240;
export const ADMIN_SIDEBAR_COLLAPSED = 64;
export const ADMIN_SIDEBAR_STORAGE_KEY = "admin-sidebar-collapsed";

function AdminSidebarCollapseToggle({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  const label = collapsed ? "展开侧栏" : "收起侧栏";

  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={label}
      title={label}
      className="absolute top-1/2 -right-3.5 z-50 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-full border border-line bg-surface text-ink-muted shadow-sm transition hover:border-brand/30 hover:text-brand"
    >
      <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d={collapsed ? "M9 6l6 6-6 6" : "M15 6l-6 6 6 6"}
        />
      </svg>
    </button>
  );
}

function NavLink({
  item,
  pathname,
  collapsed,
  onNavigate,
}: {
  item: AdminNavItem;
  pathname: string;
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const active = isAdminNavActive(pathname, item.href);
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      title={collapsed ? item.label : undefined}
      aria-label={collapsed ? item.label : undefined}
      className={`admin-nav-item ${active ? "admin-nav-item-active" : ""} ${collapsed ? "admin-nav-item-collapsed" : ""}`}
    >
      <AdminNavIcon icon={item.icon} className="h-[18px] w-[18px] shrink-0" />
      {!collapsed ? <span className="truncate">{item.label}</span> : null}
    </Link>
  );
}

type Props = {
  pathname: string;
  collapsed?: boolean;
  hideCollapseButton?: boolean;
  onToggleCollapse?: () => void;
  onNavigate?: () => void;
};

export function AdminSidebar({
  pathname,
  collapsed = false,
  hideCollapseButton,
  onToggleCollapse,
  onNavigate,
}: Props) {
  const role = useAdminAuthStore((s) => s.admin?.role);
  const [reviewMode, setReviewMode] = useState<string | null>(null);

  useEffect(() => {
    adminApi
      .getMarketplaceReviewMode()
      .then((r) => setReviewMode(r.review_mode))
      .catch(() => setReviewMode(null));
  }, []);

  const navGroups: AdminNavGroup[] = ADMIN_NAV.map((group) => ({
    ...group,
    items: group.items.filter((item) => {
      if (item.superAdminOnly && role !== "super_admin") return false;
      if (item.platformReviewOnly && reviewMode !== "platform") return false;
      return true;
    }),
  })).filter((group) => group.items.length > 0);

  const width = collapsed ? ADMIN_SIDEBAR_COLLAPSED : ADMIN_SIDEBAR_EXPANDED;

  return (
    <div className="relative min-h-screen shrink-0 overflow-visible transition-[width] duration-200 ease-out" style={{ width }}>
      <aside className="relative flex min-h-screen w-full flex-col overflow-visible border-r border-line bg-surface">
        <div
          className={`flex h-14 shrink-0 items-center border-b border-line ${collapsed ? "justify-center px-2" : "px-4"}`}
        >
          {collapsed ? (
            <Link href="/" title="行千里" aria-label="行千里" className="transition opacity-95 hover:opacity-100">
              <CompanyLogo variant="mark" size="sm" />
            </Link>
          ) : (
            <BrandHeader href="/" />
          )}
        </div>

        <nav className={`min-h-0 flex-1 overflow-y-auto py-4 ${collapsed ? "px-2" : "px-3"}`}>
          {navGroups.map((group, groupIndex) => (
            <div
              key={group.title}
              className={groupIndex > 0 ? (collapsed ? "mt-3 border-t border-line pt-3" : "mt-5") : undefined}
            >
              {!collapsed ? (
                <p className="mb-2 px-3 text-[11px] font-semibold tracking-wider text-ink-faint">{group.title}</p>
              ) : null}
              <ul className="space-y-0.5">
                {group.items.map((item) => (
                  <li key={item.href}>
                    <NavLink item={item} pathname={pathname} collapsed={collapsed} onNavigate={onNavigate} />
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        {!hideCollapseButton && onToggleCollapse ? (
          <AdminSidebarCollapseToggle collapsed={collapsed} onToggle={onToggleCollapse} />
        ) : null}
      </aside>
    </div>
  );
}
