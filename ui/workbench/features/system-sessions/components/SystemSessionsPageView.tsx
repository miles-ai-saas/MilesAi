"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { SessionListItem } from "@/features/system-sessions/components/SessionListItem";
import type { SystemSessionsPageVm } from "@/features/system-sessions/hooks/use-system-sessions-page";

const SYSTEM_SESSIONS_PAGE_DESC = "查看当前账号在各设备上的活跃登录，可强制下线可疑会话。";

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
