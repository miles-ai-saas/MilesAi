"use client";

/** 租户用户管理（链路 §3，壳层 §7 SystemShell）。 */

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { PageHeader } from "@/components/layout/PageHeader";
import type { Role, TenantUser } from "@/lib/types";

export default function SystemUsersPage() {
  const { ready } = useRequireAuth();
  const list = usePagedList(useCallback((p, s) => api.listUsers(p, s), []), { enabled: ready });
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const [roles, setRoles] = useState<Role[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [editUser, setEditUser] = useState<TenantUser | null>(null);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [roleIds, setRoleIds] = useState<string[]>([]);

  useEffect(() => {
    if (!ready) return;
    api.listAssignableRoles().then(setRoles);
  }, [ready]);

  const openCreate = () => {
    setEditUser(null);
    setUsername("");
    setEmail("");
    setPassword("");
    setPhone("");
    setRoleIds(roles[0] ? [roles[0].id] : []);
    setCreateOpen(true);
  };

  const openEdit = (u: TenantUser) => {
    setEditUser(u);
    setEmail(u.email);
    setPhone(u.phone ?? "");
    setIsActive(u.is_active);
    const ids = roles.filter((r) => u.role_codes?.includes(r.code)).map((r) => r.id);
    setRoleIds(ids);
    setCreateOpen(true);
  };

  const toggleRole = (id: string) => {
    setRoleIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const onSave = async () => {
    if (editUser) {
      await api.updateUser(editUser.id, {
        email,
        phone: phone || undefined,
        is_active: isActive,
        role_ids: roleIds,
      });
    } else {
      if (!username.trim() || !email.trim() || password.length < 6) return;
      await api.createUser({
        username: username.trim(),
        email: email.trim(),
        password,
        phone: phone || undefined,
        role_ids: roleIds,
      });
    }
    setCreateOpen(false);
    await list.reload();
  };

  const onDeactivate = (u: TenantUser) => {
    requestConfirm({
      title: "删除用户",
      message: (
        <>
          确定删除用户 <span className="font-medium">{u.username}</span>？
        </>
      ),
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deactivateUser(u.id);
        await list.reload();
      },
    });
  };

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title="用户管理"
        description="管理当前租户下的用户账号与角色分配"
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
                          删除
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
        <div className="rounded border border-line-soft p-3">
          <p className="mb-2 text-xs font-medium text-ink-muted">角色</p>
          <div className="flex flex-wrap gap-3">
            {roles.map((r) => (
              <label key={r.id} className="flex cursor-pointer items-center gap-1 text-xs">
                <input
                  type="checkbox"
                  checked={roleIds.includes(r.id)}
                  onChange={() => toggleRole(r.id)}
                />
                {r.name}
              </label>
            ))}
          </div>
        </div>
      </ResourceDialog>
      {confirmDialog}
    </div>
  );
}
