"use client";

import { useEffect, useRef, useState } from "react";
import { useAuthStore } from "@/lib/auth-store";

export function UserMenu({ variant = "sidebar" }: { variant?: "sidebar" | "header" }) {
  const user = useAuthStore((s) => s.user);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const isHeader = variant === "header";

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

  if (!user) {
    return isHeader ? null : <div className="h-14 border-t border-line-soft" />;
  }

  const initial = user.username.slice(0, 1).toUpperCase();

  return (
    <div
      ref={rootRef}
      className={`relative ${isHeader ? "" : "border-t border-line-soft p-3"}`}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={`flex items-center gap-2 rounded-lg transition ${
          isHeader
            ? `px-2 py-1.5 ${open ? "bg-brand-light" : "hover:bg-surface-muted"}`
            : `w-full px-2 py-2 text-left ${open ? "bg-brand-light" : "hover:bg-surface-muted"}`
        }`}
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand text-sm font-semibold text-brand-foreground">
          {initial}
        </span>
        {!isHeader && (
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium text-ink">{user.username}</span>
            <span className="block truncate text-xs text-ink-muted">{user.email}</span>
          </span>
        )}
        {isHeader && (
          <span className="hidden max-w-[120px] truncate text-sm font-medium text-ink md:inline">
            {user.username}
          </span>
        )}
        <svg
          className={`h-4 w-4 shrink-0 text-ink-faint transition ${open ? "rotate-180" : ""}`}
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden
        >
          <path
            fillRule="evenodd"
            d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.94a.75.75 0 111.08 1.04l-4.24 4.5a.75.75 0 01-1.08 0l-4.24-4.5a.75.75 0 01.02-1.06z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {open && (
        <div
          role="menu"
          className={`absolute z-50 overflow-hidden rounded-lg border border-line bg-surface py-1 shadow-panel ${
            isHeader
              ? "right-0 top-full mt-1 w-48"
              : "bottom-full left-3 right-3 mb-1"
          }`}
        >
          {isHeader && (
            <div className="border-b border-line-soft px-3 py-2">
              <p className="truncate text-sm font-medium text-ink">{user.username}</p>
              <p className="truncate text-xs text-ink-muted">{user.email}</p>
            </div>
          )}
          {user.is_superuser && (
            <p className="border-b border-line-soft px-3 py-2 text-xs text-brand">超级管理员</p>
          )}
          <button
            type="button"
            role="menuitem"
            className="w-full px-3 py-2 text-left text-sm text-ink-muted transition hover:bg-brand-light hover:text-brand"
            onClick={() => {
              setOpen(false);
              useAuthStore.getState().logout();
              window.location.href = "/login";
            }}
          >
            退出登录
          </button>
        </div>
      )}
    </div>
  );
}
