"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BrandHeader } from "@/components/brand/brand-header";
import { ADMIN_NAV, isAdminNavActive, type AdminNavGroup, type AdminNavItem } from "@/lib/admin-nav";
import { AdminNavIcon } from "@/components/layout/AdminNavIcon";
import { adminApi } from "@/lib/api";
import { useAdminAuthStore } from "@/lib/auth-store";

function NavLink({ item, pathname, onNavigate }: { item: AdminNavItem; pathname: string; onNavigate?: () => void }) {
  const active = isAdminNavActive(pathname, item.href);
  return (
    <Link href={item.href} onClick={onNavigate} className={`admin-nav-item ${active ? "admin-nav-item-active" : ""}`}>
      <AdminNavIcon icon={item.icon} className="h-[18px] w-[18px] shrink-0" />
      <span className="truncate">{item.label}</span>
    </Link>
  );
}

export function AdminSidebar({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
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
  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-line bg-surface">
      <div className="flex h-14 shrink-0 items-center border-b border-line px-4">
        <BrandHeader productLine="MilesAi · 管理后台" href="/" />
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {navGroups.map((group) => (
          <div key={group.title} className="mb-5 last:mb-0">
            <p className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">{group.title}</p>
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
    </aside>
  );
}
