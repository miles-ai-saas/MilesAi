"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import type { DueMilestoneItem } from "@/lib/types";

const DISMISS_KEY = "biz-milestone-dismiss-date";

function todayKey() {
  return new Date().toISOString().slice(0, 10);
}

export function BizNotificationBell() {
  const { ready } = useRequireAuth();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<DueMilestoneItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getBizNotifications(7);
      setItems(data.due_milestones ?? []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!ready) return;
    setDismissed(localStorage.getItem(DISMISS_KEY) === todayKey());
    void reload();
  }, [ready, reload]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const visibleCount = dismissed ? 0 : items.length;
  const overdueCount = items.filter((m) => m.overdue).length;

  const dismissToday = () => {
    localStorage.setItem(DISMISS_KEY, todayKey());
    setDismissed(true);
    setOpen(false);
  };

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        className="relative inline-flex h-8 w-8 items-center justify-center rounded-lg border border-line text-ink-muted transition hover:bg-surface-muted hover:text-ink"
        aria-label="业务提醒"
        onClick={() => {
          setOpen((v) => !v);
          if (!open) void reload();
        }}
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6 6 0 10-12 0v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
        {visibleCount > 0 ? (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white">
            {visibleCount > 9 ? "9+" : visibleCount}
          </span>
        ) : null}
      </button>

      {open ? (
        <div className="absolute right-0 top-full z-50 mt-2 w-80 rounded-xl border border-line bg-surface shadow-lg">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <div>
              <p className="text-sm font-semibold text-ink">业务提醒</p>
              <p className="text-xs text-ink-muted">7 天内到期里程碑</p>
            </div>
            {visibleCount > 0 ? (
              <button type="button" className="text-xs text-ink-muted hover:text-brand" onClick={dismissToday}>
                今日不再提示
              </button>
            ) : null}
          </div>

          <div className="max-h-80 overflow-y-auto p-2">
            {loading ? (
              <p className="px-2 py-6 text-center text-sm text-ink-muted">加载中…</p>
            ) : items.length === 0 ? (
              <p className="px-2 py-6 text-center text-sm text-ink-muted">暂无到期里程碑</p>
            ) : dismissed ? (
              <p className="px-2 py-6 text-center text-sm text-ink-muted">今日提醒已关闭</p>
            ) : (
              <ul className="space-y-1">
                {items.map((m) => (
                  <li key={m.id}>
                    <Link
                      href={`/business/projects/detail?id=${m.project_id}&tab=workpackages`}
                      className="block rounded-lg px-3 py-2 transition hover:bg-surface-muted"
                      onClick={() => setOpen(false)}
                    >
                      <p className="text-sm font-medium text-ink">{m.title}</p>
                      <p className="text-xs text-ink-muted">
                        {m.project_name}
                        {m.due_date ? ` · ${m.due_date}` : ""}
                        {m.overdue ? " · 已逾期" : ""}
                      </p>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {!dismissed && overdueCount > 0 ? (
            <div className="border-t border-line px-4 py-2 text-xs text-amber-700">
              {overdueCount} 项已逾期，请尽快处理
            </div>
          ) : null}

          <div className="border-t border-line px-4 py-2">
            <Link href="/business/dashboard" className="text-xs text-brand hover:underline" onClick={() => setOpen(false)}>
              打开业务工作台
            </Link>
          </div>
        </div>
      ) : null}
    </div>
  );
}
