"use client";

/** 系统管理侧栏（链路 §7）。 */

import Link from "next/link";
import { BrandHeader } from "@/components/brand/brand-header";
import { SystemNavIcon } from "@/components/layout/SystemNavIcon";
import { filterSystemNav, isNavActive, type SystemNavItem } from "@/lib/nav-config";
import { useAuthStore } from "@/lib/auth-store";

function NavLink({ item, pathname, onNavigate }: { item: SystemNavItem; pathname: string; onNavigate?: () => void }) {
  const active = isNavActive(pathname, item.href);
  return (
    <Link href={item.href} onClick={onNavigate} className={`nav-item ${active ? "nav-item-active" : "hover:bg-surface-muted"}`}>
      <SystemNavIcon icon={item.icon} className="h-[18px] w-[18px] shrink-0" />
      <span className="truncate">{item.label}</span>
    </Link>
  );
}

export function SystemSidebar({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  const user = useAuthStore((s) => s.user);
  const navGroups = filterSystemNav(user);

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-line bg-surface">
      <div className="flex h-14 shrink-0 items-center border-b border-line px-4">
        <BrandHeader href="/system/users" />
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
