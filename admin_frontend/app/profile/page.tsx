"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { adminApi } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export default function ProfilePage() {
  const ready = useRequireAdmin();
  const [me, setMe] = useState<{ username: string; role: string } | null>(null);
  const [sessions, setSessions] = useState<{ admin_id: string; username: string; role: string }[]>(
    [],
  );
  const [oldPwd, setOldPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!ready) return;
    Promise.all([adminApi.me(), adminApi.listSessions()]).then(([m, s]) => {
      setMe(m);
      setSessions(s);
    });
  }, [ready]);

  const changePwd = async () => {
    setErr("");
    setMsg("");
    try {
      await adminApi.changePassword(oldPwd, newPwd);
      setMsg("密码已修改");
      setOldPwd("");
      setNewPwd("");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "修改失败");
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
        {msg && <p className="mt-2 text-sm text-emerald-600">{msg}</p>}
        {err && <p className="mt-2 text-sm text-red-600">{err}</p>}
      </section>

      <section className="card p-4">
        <h2 className="text-sm font-semibold text-ink">在线会话</h2>
        <ul className="mt-3 space-y-2 text-sm">
          {sessions.map((s) => (
            <li key={s.admin_id} className="rounded-lg bg-surface-muted px-3 py-2">
              {s.username}
              <span className="text-ink-faint"> · {s.role}</span>
              <span className="ml-2 font-mono text-xs text-ink-faint">
                {s.admin_id.slice(0, 8)}…
              </span>
            </li>
          ))}
          {sessions.length === 0 && <li className="text-ink-faint">无活跃会话</li>}
        </ul>
      </section>
    </div>
  );
}
