"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import type { SystemSessionsPageVm } from "@/features/system-sessions/hooks/use-system-sessions-page";
import type { UserSession } from "@/lib/types";

const SYSTEM_SESSIONS_PAGE_DESC = "查看当前账号在各设备上的活跃登录，可强制下线可疑会话。";

function formatSessionTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-CN");
}

function SessionListItem({ session, onRevoke }: { session: UserSession; onRevoke: () => void }) {
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

export function SystemSessionsPageView({ vm }: { vm: SystemSessionsPageVm }) {
  const { sessions, loading, msg, load, revoke, revokeOthers } = vm;

  return (
    <div className="w-full">
      <PageHeader title="登录会话" description={SYSTEM_SESSIONS_PAGE_DESC} />

      {msg && <p className="mb-4 rounded-lg border border-line bg-brand-light/40 px-4 py-2 text-sm text-ink">{msg}</p>}

      <div className="mb-4 flex flex-wrap gap-2">
        <button type="button" className="btn-sm-outline" disabled={loading} onClick={() => void load()}>
          刷新
        </button>
        <button type="button" className="btn-sm-outline text-red-600" disabled={loading || sessions.length <= 1} onClick={() => void revokeOthers()}>
          下线其他设备
        </button>
      </div>

      {loading ? (
        <p className="text-sm text-ink-muted">加载中…</p>
      ) : sessions.length === 0 ? (
        <p className="text-sm text-ink-faint">暂无会话记录，请重新登录后查看。</p>
      ) : (
        <ul className="space-y-3">
          {sessions.map((s) => (
            <SessionListItem key={s.jti} session={s} onRevoke={() => void revoke(s.jti)} />
          ))}
        </ul>
      )}
    </div>
  );
}
