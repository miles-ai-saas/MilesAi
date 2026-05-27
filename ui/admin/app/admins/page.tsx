"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { adminApi, type PlatformAdmin } from "@/lib/api";
import { useAdminAuthStore, useRequireAdmin } from "@/lib/auth-store";

const ROLES = [
  { value: "ops", label: "运营 (ops)" },
  { value: "billing", label: "计费 (billing)" },
  { value: "security", label: "安全 (security)" },
  { value: "viewer", label: "只读 (viewer)" },
  { value: "super_admin", label: "超级管理员" },
];

export default function AdminsPage() {
  const ready = useRequireAdmin();
  const currentRole = useAdminAuthStore((s) => s.admin?.role);
  const currentId = useAdminAuthStore((s) => s.admin?.id);
  const [admins, setAdmins] = useState<PlatformAdmin[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState("ops");
  const [resetId, setResetId] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const reload = async () => {
    const res = await adminApi.listAdmins();
    setAdmins(res.items);
  };

  useEffect(() => {
    if (!ready) return;
    if (currentRole !== "super_admin") return;
    reload().catch(() => undefined);
  }, [ready, currentRole]);

  if (ready && currentRole !== "super_admin") {
    return (
      <div>
        <PageHeader title="平台管理员" description="仅超级管理员可访问" />
        <p className="text-sm text-ink-muted">当前账号无权限查看此页面。</p>
      </div>
    );
  }

  const onCreate = async () => {
    setErr("");
    setMsg("");
    try {
      await adminApi.createAdmin({
        username: username.trim(),
        password,
        display_name: displayName.trim() || undefined,
        role,
      });
      setShowForm(false);
      setUsername("");
      setPassword("");
      setDisplayName("");
      setMsg("管理员已创建");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "创建失败");
    }
  };

  const onDisable = async (id: string) => {
    if (!confirm("确定禁用该管理员？")) return;
    setErr("");
    try {
      await adminApi.disableAdmin(id);
      setMsg("已禁用");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "操作失败");
    }
  };

  const onResetPassword = async () => {
    if (!resetId || !newPassword) return;
    setErr("");
    try {
      await adminApi.resetAdminPassword(resetId, newPassword);
      setResetId(null);
      setNewPassword("");
      setMsg("密码已重置");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "重置失败");
    }
  };

  return (
    <div>
      <PageHeader
        title="平台管理员"
        description="创建运营账号、分配角色与重置密码"
        action={
          <button type="button" className="btn-primary" onClick={() => setShowForm((v) => !v)}>
            {showForm ? "取消" : "新建管理员"}
          </button>
        }
      />

      {msg && <p className="mb-4 text-sm text-emerald-600">{msg}</p>}
      {err && <p className="mb-4 text-sm text-red-600">{err}</p>}

      {showForm && (
        <section className="card mb-6 p-4">
          <h2 className="text-sm font-semibold text-ink">新建管理员</h2>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <input
              className="input-field"
              placeholder="用户名"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
            <input
              className="input-field"
              type="password"
              placeholder="初始密码"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <input
              className="input-field"
              placeholder="显示名称（可选）"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
            />
            <select className="input-field" value={role} onChange={(e) => setRole(e.target.value)}>
              {ROLES.filter((r) => r.value !== "super_admin").map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>
          <button type="button" className="btn-primary mt-3" onClick={onCreate}>
            保存
          </button>
        </section>
      )}

      <section className="card p-4">
        <div className="admin-table-wrap border-0">
          <table className="admin-table">
            <thead>
              <tr>
                <th>用户名</th>
                <th>显示名</th>
                <th className="col-center">角色</th>
                <th className="col-center">状态</th>
                <th className="col-actions">操作</th>
              </tr>
            </thead>
            <tbody>
              {admins.map((a) => (
                <tr key={a.id}>
                  <td className="cell-primary">{a.username}</td>
                  <td className="cell-muted">{a.display_name || "—"}</td>
                  <td className="col-center">
                    <span className="badge bg-brand-light text-ink">{a.role}</span>
                  </td>
                  <td className="col-center">
                    {a.is_active ? (
                      <span className="text-emerald-600">启用</span>
                    ) : (
                      <span className="text-ink-faint">已禁用</span>
                    )}
                  </td>
                  <td className="col-actions">
                    {a.is_active && (
                      <button
                        type="button"
                        className="text-brand hover:underline"
                        onClick={() => setResetId(a.id)}
                      >
                        重置密码
                      </button>
                    )}
                    {a.is_active && a.id !== currentId && (
                      <button
                        type="button"
                        className="text-red-600 hover:underline"
                        onClick={() => onDisable(a.id)}
                      >
                        禁用
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {resetId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
          <div className="card w-full max-w-sm p-4">
            <h3 className="font-semibold text-ink">重置密码</h3>
            <input
              className="input-field mt-3 w-full"
              type="password"
              placeholder="新密码（至少 6 位）"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" className="btn-secondary" onClick={() => setResetId(null)}>
                取消
              </button>
              <button type="button" className="btn-primary" onClick={onResetPassword}>
                确认
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
