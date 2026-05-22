"use client";

import Link from "next/link";
import { SystemNavIcon } from "@/components/layout/SystemNavIcon";
import { SYSTEM_NAV, isNavActive, type SystemNavItem } from "@/lib/nav-config";

function NavLink({
  item,
  pathname,
  onNavigate,
}: {
  item: SystemNavItem;
  pathname: string;
  onNavigate?: () => void;
}) {
  const active = isNavActive(pathname, item.href);
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      className={`nav-item ${active ? "nav-item-active" : "hover:bg-surface-muted"}`}
    >
      <SystemNavIcon icon={item.icon} className="h-[18px] w-[18px] shrink-0" />
      <span className="truncate">{item.label}</span>
    </Link>
  );
}

export function SystemSidebar({
  pathname,
  onNavigate,
}: {
  pathname: string;
  onNavigate?: () => void;
}) {
  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-line bg-surface">
      <div className="flex h-14 shrink-0 items-center gap-2.5 border-b border-line px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-light text-sm font-bold text-brand">
          A
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-brand">AiEngine</p>
          <p className="truncate text-[11px] text-ink-faint">系统管理</p>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {SYSTEM_NAV.map((group) => (
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
    </aside>
  );
}
