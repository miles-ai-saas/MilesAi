"use client";

import type { AdminsPageVm } from "@/features/admins/hooks/use-admins-page";
import { ADMIN_ROLES } from "@/features/admins/lib/admins-page-shared";

export function AdminsCreateFormSection({ vm }: { vm: AdminsPageVm }) {
  const { showForm, username, setUsername, password, setPassword, displayName, setDisplayName, role, setRole, onCreate } = vm;
  if (!showForm) return null;

  return (
    <section className="card p-5">
      <h2 className="text-sm font-semibold text-ink">新建管理员</h2>
      <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <input className="input-field" placeholder="用户名" value={username} onChange={(e) => setUsername(e.target.value)} />
        <input className="input-field" type="password" placeholder="初始密码" value={password} onChange={(e) => setPassword(e.target.value)} />
        <input className="input-field" placeholder="显示名称（可选）" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
        <select className="input-field" value={role} onChange={(e) => setRole(e.target.value)}>
          {ADMIN_ROLES.filter((r) => r.value !== "super_admin").map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
      </div>
      <button type="button" className="btn-primary mt-3" onClick={() => void onCreate()}>
        保存
      </button>
    </section>
  );
}
