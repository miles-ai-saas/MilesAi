"use client";

import type { UserSession } from "@/lib/types";

function formatSessionTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-CN");
}

export function SessionListItem({ session, onRevoke }: { session: UserSession; onRevoke: () => void }) {
  return (
    <li className={`rounded-xl border border-line bg-surface px-4 py-3 shadow-card ${session.is_current ? "ring-1 ring-brand/30" : ""}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {session.is_current ? <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700">当前会话</span> : null}
            <span className="text-sm font-medium text-ink">{session.user_agent?.slice(0, 80) || "未知设备"}</span>
          </div>
          <p className="mt-1 text-xs text-ink-muted">
            IP {session.ip || "—"} · 登录 {formatSessionTime(session.created_at)}
            {session.last_seen_at ? ` · 活跃 ${formatSessionTime(session.last_seen_at)}` : ""}
          </p>
        </div>
        {!session.is_current ? (
          <button type="button" className="text-xs text-red-600 hover:underline" onClick={onRevoke}>
            强制下线
          </button>
        ) : null}
      </div>
    </li>
  );
}
