"use client";

/** 运营后台顶栏用户菜单：账号信息、账号安全、退出登录。 */

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ADMIN_ACCOUNT_NAV } from "@/lib/admin-nav";

export function AdminUserMenu({ username, role, onLogout }: { username?: string; role?: string; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  if (!username) return null;

  const initial = username.slice(0, 1).toUpperCase();

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={`flex items-center gap-2 rounded-lg px-2 py-1.5 transition ${open ? "bg-brand-light" : "hover:bg-surface-muted"}`}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="用户菜单"
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand text-sm font-semibold text-brand-foreground">{initial}</span>
        <span className="hidden max-w-[120px] truncate text-sm font-medium text-ink md:inline">{username}</span>
        <svg className={`h-4 w-4 shrink-0 text-ink-faint transition ${open ? "rotate-180" : ""}`} viewBox="0 0 20 20" fill="currentColor" aria-hidden>
          <path
            fillRule="evenodd"
            d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.94a.75.75 0 111.08 1.04l-4.24 4.5a.75.75 0 01-1.08 0l-4.24-4.5a.75.75 0 01.02-1.06z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {open && (
        <div role="menu" className="absolute right-0 top-full z-50 mt-1 w-52 overflow-hidden rounded-lg border border-line bg-surface py-1 shadow-panel">
          <div className="border-b border-line-soft px-3 py-2.5">
            <p className="truncate text-sm font-medium text-ink">{username}</p>
            {role && <p className="truncate text-xs text-ink-muted">{role}</p>}
          </div>
          <Link
            href={ADMIN_ACCOUNT_NAV.href}
            role="menuitem"
            className="block px-3 py-2 text-sm text-ink-muted transition hover:bg-brand-light hover:text-brand"
            onClick={() => setOpen(false)}
          >
            {ADMIN_ACCOUNT_NAV.label}
          </Link>
          <button
            type="button"
            role="menuitem"
            className="w-full border-t border-line-soft px-3 py-2 text-left text-sm text-ink-muted transition hover:bg-brand-light hover:text-brand"
            onClick={() => {
              setOpen(false);
              onLogout();
            }}
          >
            退出登录
          </button>
        </div>
      )}
    </div>
  );
}
