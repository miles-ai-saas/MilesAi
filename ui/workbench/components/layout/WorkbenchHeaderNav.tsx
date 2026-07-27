"use client";

/** 工作台顶栏域级导航（链路 §7）：`WORKBENCH_NAV` 分组 + 下拉二级菜单。 */

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { isAgentsChatNavHref, resolveAgentsChatEntryHref } from "@/features/agents/lib/agents-chat-href";
import { WORKBENCH_NAV, isNavActive, isNavGroupActive, type NavGroup } from "@/lib/nav-config";

function resolveNavItemHref(href: string): string {
  return isAgentsChatNavHref(href) ? resolveAgentsChatEntryHref() : href;
}

function NavChevron({ open }: { open: boolean }) {
  return (
    <svg className={`h-3.5 w-3.5 shrink-0 text-ink-faint transition ${open ? "rotate-180" : ""}`} viewBox="0 0 20 20" fill="currentColor" aria-hidden>
      <path
        fillRule="evenodd"
        d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.94a.75.75 0 111.08 1.04l-4.24 4.5a.75.75 0 01-1.08 0l-4.24-4.5a.75.75 0 01.02-1.06z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function WorkbenchNavGroup({
  group,
  pathname,
  open,
  onToggle,
  onClose,
}: {
  group: NavGroup;
  pathname: string;
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
}) {
  const rootRef = useRef<HTMLDivElement>(null);
  const groupActive = isNavGroupActive(pathname, group);
  const singleItem = group.items.length === 1 ? group.items[0] : null;

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  if (singleItem) {
    const active = isNavActive(pathname, singleItem.href);
    return (
      <Link
        href={resolveNavItemHref(singleItem.href)}
        className={`header-nav-item shrink-0 ${active ? "header-nav-item-active" : ""}`}
      >
        {group.title}
      </Link>
    );
  }

  return (
    <div ref={rootRef} className="relative shrink-0">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-haspopup="menu"
        className={`header-nav-item inline-flex items-center gap-1 ${groupActive ? "header-nav-item-active" : ""}`}
      >
        {group.title}
        <NavChevron open={open} />
      </button>
      {open ? (
        <div role="menu" className="absolute left-0 top-full z-50 mt-1 min-w-[10.5rem] overflow-hidden rounded-lg border border-line bg-surface py-1 shadow-panel">
          {group.items.map((item) => {
            const active = isNavActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                role="menuitem"
                href={resolveNavItemHref(item.href)}
                onClick={onClose}
                className={`block px-3 py-2 text-sm transition ${active ? "bg-brand-light font-medium text-brand" : "text-ink-muted hover:bg-surface-muted hover:text-ink"}`}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

export function WorkbenchHeaderNav({ pathname }: { pathname: string }) {
  const [openGroup, setOpenGroup] = useState<string | null>(null);

  useEffect(() => {
    setOpenGroup(null);
  }, [pathname]);

  return (
    <nav className="flex min-w-0 flex-1 items-center gap-1 px-2" aria-label="工作台导航">
      {WORKBENCH_NAV.map((group) => (
        <WorkbenchNavGroup
          key={group.title}
          group={group}
          pathname={pathname}
          open={openGroup === group.title}
          onToggle={() => setOpenGroup((current) => (current === group.title ? null : group.title))}
          onClose={() => setOpenGroup(null)}
        />
      ))}
    </nav>
  );
}
