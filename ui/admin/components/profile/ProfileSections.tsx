"use client";

import type { ProfilePageVm } from "@/hooks/use-profile-page";

export function ProfilePasswordSection({ vm }: { vm: ProfilePageVm }) {
  const { oldPwd, setOldPwd, newPwd, setNewPwd, err, changePwd } = vm;

  return (
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
      <button type="button" onClick={() => void changePwd()} className="btn-primary mt-3">
        保存密码
      </button>
      {err && <p className="mt-2 text-sm text-red-600">{err}</p>}
    </section>
  );
}

export function ProfileSessionsSection({ vm }: { vm: ProfilePageVm }) {
  const { sessions, msg, revoking, revokeSession } = vm;

  return (
    <section className="card p-4">
      <h2 className="text-sm font-semibold text-ink">在线会话</h2>
      <ul className="admin-data-list mt-3">
        {sessions.map((s) => (
          <li key={s.admin_id} className="admin-data-row flex items-center justify-between gap-2">
            <div className="min-w-0">
              {s.username}
              <span className="text-ink-faint"> · {s.role}</span>
              {s.is_current && <span className="ml-2 rounded bg-brand-light px-1.5 py-0.5 text-xs text-brand">当前</span>}
            </div>
            {!s.is_current && (
              <button
                type="button"
                className="shrink-0 text-xs text-red-600 hover:underline disabled:opacity-50"
                disabled={revoking === s.admin_id}
                onClick={() => void revokeSession(s.admin_id)}
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
  );
}
