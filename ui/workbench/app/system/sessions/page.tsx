"use client";

/** 当前用户登录会话：查看设备与强制下线。 */

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { PageHeader } from "@/components/layout/PageHeader";
import type { UserSession } from "@/lib/types";

function formatTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-CN");
}

export default function SystemSessionsPage() {
  const { ready } = useRequireAuth();
  const [sessions, setSessions] = useState<UserSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setMsg("");
    try {
      setSessions(await api.listMySessions());
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (ready) void load();
  }, [ready, load]);

  const revoke = async (jti: string) => {
    setMsg("");
    try {
      await api.revokeMySession(jti);
      setMsg("已强制下线该设备");
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "操作失败");
    }
  };

  const revokeOthers = async () => {
    setMsg("");
    try {
      const res = await api.revokeOtherSessions();
      setMsg(`已下线其他 ${res.revoked} 个会话`);
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "操作失败");
    }
  };

  return (
    <div className="w-full">
      <PageHeader title="登录会话" description="查看当前账号在各设备上的活跃登录，可强制下线可疑会话。" />

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
            <li key={s.jti} className={`rounded-xl border border-line bg-surface px-4 py-3 shadow-card ${s.is_current ? "ring-1 ring-brand/30" : ""}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    {s.is_current ? <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700">当前会话</span> : null}
                    <span className="text-sm font-medium text-ink">{s.user_agent?.slice(0, 80) || "未知设备"}</span>
                  </div>
                  <p className="mt-1 text-xs text-ink-muted">
                    IP {s.ip || "—"} · 登录 {formatTime(s.created_at)}
                    {s.last_seen_at ? ` · 活跃 ${formatTime(s.last_seen_at)}` : ""}
                  </p>
                </div>
                {!s.is_current ? (
                  <button type="button" className="text-xs text-red-600 hover:underline" onClick={() => void revoke(s.jti)}>
                    强制下线
                  </button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
