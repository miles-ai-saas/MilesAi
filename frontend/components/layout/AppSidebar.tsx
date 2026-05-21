"use client";

import Link from "next/link";
import { SYSTEM_NAV, isNavActive } from "@/lib/nav-config";

export function AppSidebar({ pathname }: { pathname: string }) {
  return (
    <aside className="flex w-52 shrink-0 flex-col border-r border-line bg-surface">
      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {SYSTEM_NAV.map((group) => (
          <div key={group.title} className="mb-5">
            <p className="mb-1.5 px-3 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
              {group.title}
            </p>
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const active = isNavActive(pathname, item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={`nav-item ${active ? "nav-item-active" : ""}`}
                    >
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
    </aside>
  );
}
