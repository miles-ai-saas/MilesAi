"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { PageHeader } from "@/components/layout/PageHeader";
import type { TenantUser } from "@/lib/types";

export default function SystemUsersPage() {
  const { ready } = useRequireAuth();
  const list = usePagedList(useCallback((p, s) => api.listUsers(p, s), []), { enabled: ready });

  const [createOpen, setCreateOpen] = useState(false);
  const [editUser, setEditUser] = useState<TenantUser | null>(null);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [isActive, setIsActive] = useState(true);

  const openCreate = () => {
    setEditUser(null);
    setUsername("");
    setEmail("");
    setPassword("");
    setPhone("");
    setCreateOpen(true);
  };

  const openEdit = (u: TenantUser) => {
    setEditUser(u);
    setEmail(u.email);
    setPhone(u.phone ?? "");
    setIsActive(u.is_active);
    setCreateOpen(true);
  };

  const onSave = async () => {
    if (editUser) {
      await api.updateUser(editUser.id, {
        email,
        phone: phone || undefined,
        is_active: isActive,
      });
    } else {
      if (!username.trim() || !email.trim() || password.length < 6) return;
      await api.createUser({
        username: username.trim(),
        email: email.trim(),
        password,
        phone: phone || undefined,
      });
    }
    setCreateOpen(false);
    await list.reload();
  };

  const onDeactivate = async (u: TenantUser) => {
    if (!confirm(`确定禁用用户「${u.username}」？`)) return;
    await api.deactivateUser(u.id);
    await list.reload();
  };

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title="用户管理"
        description="管理当前租户下的用户账号"
        action={
          <button type="button" className="btn-primary" onClick={openCreate}>
            新建用户
          </button>
        }
      />
      {list.loading ? (
        <p className="text-sm text-ink-muted">加载中…</p>
      ) : (
        <>
          <div className="card overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line bg-surface-muted text-xs text-ink-muted">
                <tr>
                  <th className="px-4 py-2">用户名</th>
                  <th className="px-4 py-2">邮箱</th>
                  <th className="px-4 py-2">状态</th>
                  <th className="px-4 py-2">角色</th>
                  <th className="px-4 py-2 text-right">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line-soft">
                {list.items.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-ink-faint">
                      暂无用户
                    </td>
                  </tr>
                )}
                {list.items.map((u: TenantUser) => (
                  <tr key={u.id}>
                    <td className="px-4 py-3 font-medium text-ink">{u.username}</td>
                    <td className="px-4 py-3 text-ink-muted">{u.email}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded px-2 py-0.5 text-xs ${
                          u.is_active ? "bg-brand-light text-brand" : "bg-surface-muted text-ink-faint"
                        }`}
                      >
                        {u.is_active ? "启用" : "禁用"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-ink-muted">
                      {u.role_codes?.join(", ") || "—"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        className="mr-3 text-xs text-brand hover:underline"
                        onClick={() => openEdit(u)}
                      >
                        编辑
                      </button>
                      {u.is_active && (
                        <button
                          type="button"
                          className="text-xs text-red-600 hover:underline"
                          onClick={() => onDeactivate(u)}
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
          <ResourceListFooter
            className="mt-3"
            page={list.page}
            size={list.size}
            total={list.total}
            onPageChange={list.setPage}
          />
        </>
      )}

      <ResourceDialog
        open={createOpen}
        title={editUser ? "编辑用户" : "新建用户"}
        onClose={() => setCreateOpen(false)}
        footer={
          <>
            <button type="button" className="btn-ghost" onClick={() => setCreateOpen(false)}>
              取消
            </button>
            <button type="button" className="btn-primary" onClick={onSave}>
              保存
            </button>
          </>
        }
      >
        {!editUser && (
          <input
            className="input-field w-full"
            placeholder="用户名"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        )}
        <input
          className="input-field w-full"
          placeholder="邮箱"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        {!editUser && (
          <input
            className="input-field w-full"
            placeholder="密码（至少 6 位）"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        )}
        <input
          className="input-field w-full"
          placeholder="手机号（可选）"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
        />
        {editUser && (
          <label className="flex items-center gap-2 text-sm text-ink-muted">
            <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
            账号启用
          </label>
        )}
      </ResourceDialog>
    </div>
  );
}
