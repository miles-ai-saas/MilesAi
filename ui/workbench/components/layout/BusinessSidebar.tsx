"use client";

/** 业务中心侧栏（参考 SystemSidebar）。 */

import Link from "next/link";
import { BrandHeader } from "@/components/brand/brand-header";
import { CompanyLogo } from "@/components/brand/company-logo";
import { SidebarCollapseButton } from "@milesai/ui-shared/ui/sidebar-collapse-button";
import { BizNavIcon } from "@/components/layout/BizNavIcon";
import { filterBusinessNav, isNavActive, type BizNavItem } from "@/lib/nav-config";
import { useAuthStore } from "@/lib/auth-store";

export const BIZ_SIDEBAR_EXPANDED = 240;
export const BIZ_SIDEBAR_COLLAPSED = 64;
export const BIZ_SIDEBAR_STORAGE_KEY = "biz-sidebar-collapsed";

function NavLink({
  item,
  pathname,
  collapsed,
  onNavigate,
}: {
  item: BizNavItem;
  pathname: string;
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const active = isNavActive(pathname, item.href);
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      title={collapsed ? item.label : undefined}
      aria-label={collapsed ? item.label : undefined}
      className={`nav-item ${active ? "nav-item-active" : ""} ${collapsed ? "nav-item-collapsed" : ""}`}
    >
      <BizNavIcon icon={item.icon} className="h-[18px] w-[18px] shrink-0" />
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

export function BusinessSidebar({
  pathname,
  collapsed = false,
  hideCollapseButton,
  onToggleCollapse,
  onNavigate,
}: Props) {
  const user = useAuthStore((s) => s.user);
  const navGroups = filterBusinessNav(user);
  const width = collapsed ? BIZ_SIDEBAR_COLLAPSED : BIZ_SIDEBAR_EXPANDED;

  return (
    <div className="relative h-full shrink-0 overflow-visible transition-[width] duration-200 ease-out" style={{ width }}>
      <aside className="flex h-full w-full flex-col border-r border-line bg-surface shadow-sm">
        <div
          className={`flex h-14 shrink-0 items-center border-b border-line ${collapsed ? "justify-center px-2" : "px-4"}`}
        >
          {collapsed ? (
            <Link href="/business/dashboard" title="行千里" aria-label="行千里" className="transition opacity-95 hover:opacity-100">
              <CompanyLogo variant="mark" size="sm" />
            </Link>
          ) : (
            <BrandHeader href="/business/dashboard" />
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
      </aside>

      {onToggleCollapse ? (
        <SidebarCollapseButton
          side="left"
          collapsed={collapsed}
          onToggle={onToggleCollapse}
          hidden={hideCollapseButton}
        />
      ) : null}
    </div>
  );
}
