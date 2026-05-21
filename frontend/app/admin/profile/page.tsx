"use client";

import { useEffect, useState } from "react";
import { adminApi } from "@/lib/admin-api";
import { useRequireAdmin } from "@/lib/admin-auth-store";

export default function AdminProfilePage() {
  const ready = useRequireAdmin();
  const [me, setMe] = useState<{ username: string; role: string } | null>(null);
  const [sessions, setSessions] = useState<{ admin_id: string; username: string }[]>([]);
  const [oldPwd, setOldPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!ready) return;
    Promise.all([adminApi.me(), adminApi.listSessions()]).then(([m, s]) => {
      setMe(m);
      setSessions(s);
    });
  }, [ready]);

  const changePwd = async () => {
    await adminApi.changePassword(oldPwd, newPwd);
    setMsg("密码已修改");
    setOldPwd("");
    setNewPwd("");
  };

  return (
    <div className="max-w-lg space-y-6">
      <h1 className="text-xl font-bold">账号安全</h1>
      {me && (
        <p className="text-sm text-slate-600">
          当前账号：{me.username}（{me.role}）
        </p>
      )}

      <section className="rounded-lg border bg-white p-4">
        <h2 className="text-sm font-semibold">修改密码</h2>
        <input
          type="password"
          className="mt-2 block w-full rounded border px-3 py-2 text-sm"
          placeholder="原密码"
          value={oldPwd}
          onChange={(e) => setOldPwd(e.target.value)}
        />
        <input
          type="password"
          className="mt-2 block w-full rounded border px-3 py-2 text-sm"
          placeholder="新密码"
          value={newPwd}
          onChange={(e) => setNewPwd(e.target.value)}
        />
        <button type="button" onClick={changePwd} className="mt-3 rounded bg-brand px-4 py-2 text-sm text-white">
          保存密码
        </button>
        {msg && <p className="mt-2 text-sm text-emerald-600">{msg}</p>}
      </section>

      <section className="rounded-lg border bg-white p-4">
        <h2 className="text-sm font-semibold">在线会话</h2>
        <ul className="mt-3 space-y-2 text-sm">
          {sessions.map((s) => (
            <li key={s.admin_id} className="rounded bg-slate-50 px-3 py-2">
              {s.username} — {s.admin_id.slice(0, 8)}…
            </li>
          ))}
          {sessions.length === 0 && <li className="text-slate-400">无活跃会话</li>}
        </ul>
      </section>
    </div>
  );
}
