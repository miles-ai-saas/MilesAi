"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { adminApi } from "@/lib/api";
import { useAdminAuthStore, useRequireAdmin } from "@/lib/auth-store";

export default function ProfilePage() {
  const ready = useRequireAdmin();
  const router = useRouter();
  const currentAdmin = useAdminAuthStore((s) => s.admin);
  const [me, setMe] = useState<{ username: string; role: string } | null>(null);
  const [sessions, setSessions] = useState<
    { admin_id: string; username: string; role: string; is_current: boolean }[]
  >([]);
  const [oldPwd, setOldPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [revoking, setRevoking] = useState<string | null>(null);

  const reload = async () => {
    const [m, s] = await Promise.all([adminApi.me(), adminApi.listSessions()]);
    setMe(m);
    setSessions(s);
  };

  useEffect(() => {
    if (!ready) return;
    reload().catch(() => undefined);
  }, [ready]);

  const changePwd = async () => {
    setErr("");
    setMsg("");
    try {
      await adminApi.changePassword(oldPwd, newPwd);
      await adminApi.logout();
      router.push("/login?msg=password_changed");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "修改失败");
    }
  };

  const revokeSession = async (adminId: string) => {
    setRevoking(adminId);
    setErr("");
    try {
      await adminApi.revokeSession(adminId);
      if (adminId === currentAdmin?.id) {
        await adminApi.logout();
        router.push("/login");
        return;
      }
      await reload();
      setMsg("会话已下线");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "操作失败");
    } finally {
      setRevoking(null);
    }
  };

  return (
    <div className="max-w-lg">
      <PageHeader title="账号安全" description="修改密码与查看在线会话" />

      {me && (
        <p className="mb-6 text-sm text-ink-muted">
          当前账号：<span className="font-medium text-ink">{me.username}</span>
          <span className="text-ink-faint"> · {me.role}</span>
        </p>
      )}

      <section className="card mb-6 p-4">
        <h2 className="text-sm font-semibold text-ink">修改密码</h2>
        <p className="mt-1 text-xs text-ink-muted">修改成功后将退出所有设备，需重新登录。</p>
        <input
          type="password"
          className="input-field mt-3"
          placeholder="原密码"
          value={oldPwd}
          onChange={(e) => setOldPwd(e.target.value)}
          autoComplete="current-password"
        />
        <input
          type="password"
          className="input-field mt-2"
          placeholder="新密码（至少 6 位）"
          value={newPwd}
          onChange={(e) => setNewPwd(e.target.value)}
          autoComplete="new-password"
        />
        <button type="button" onClick={changePwd} className="btn-primary mt-3">
          保存密码
        </button>
        {err && <p className="mt-2 text-sm text-red-600">{err}</p>}
      </section>

      <section className="card p-4">
        <h2 className="text-sm font-semibold text-ink">在线会话</h2>
        <ul className="mt-3 space-y-2 text-sm">
          {sessions.map((s) => (
            <li
              key={s.admin_id}
              className="flex items-center justify-between gap-2 rounded-lg bg-surface-muted px-3 py-2"
            >
              <div className="min-w-0">
                {s.username}
                <span className="text-ink-faint"> · {s.role}</span>
                {s.is_current && (
                  <span className="ml-2 rounded bg-brand-light px-1.5 py-0.5 text-xs text-brand">
                    当前
                  </span>
                )}
              </div>
              {!s.is_current && (
                <button
                  type="button"
                  className="shrink-0 text-xs text-red-600 hover:underline disabled:opacity-50"
                  disabled={revoking === s.admin_id}
                  onClick={() => revokeSession(s.admin_id)}
                >
                  {revoking === s.admin_id ? "处理中…" : "强制下线"}
                </button>
              )}
            </li>
          ))}
          {sessions.length === 0 && <li className="text-ink-faint">无活跃会话</li>}
        </ul>
        {msg && <p className="mt-2 text-sm text-emerald-600">{msg}</p>}
      </section>
    </div>
  );
}
