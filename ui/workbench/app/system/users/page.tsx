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
  const { ready, user: currentUser } = useRequireAuth();
  const list = usePagedList(useCallback((p, s) => api.listUsers(p, s), []), { enabled: ready });
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const [roles, setRoles] = useState<Role[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [editUser, setEditUser] = useState<TenantUser | null>(null);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [roleIds, setRoleIds] = useState<string[]>([]);
  const [resetUser, setResetUser] = useState<TenantUser | null>(null);
  const [resetPassword, setResetPassword] = useState("");
  const [batchRolesOpen, setBatchRolesOpen] = useState(false);
  const [batchRoleIds, setBatchRoleIds] = useState<string[]>([]);

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

  const onResetPassword = (u: TenantUser) => {
    setResetUser(u);
    setResetPassword("");
  };

  const onConfirmResetPassword = async () => {
    if (!resetUser || resetPassword.length < 6) return;
    await api.resetUserPassword(resetUser.id, resetPassword);
    setResetUser(null);
    setResetPassword("");
    alert("密码已重置，该用户所有会话已下线");
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const toggleSelectAll = () => {
    const selectable = list.items
      .filter((u: TenantUser) => u.id !== currentUser?.id)
      .map((u: TenantUser) => u.id);
    if (selectable.length > 0 && selectable.every((id) => selectedIds.includes(id))) {
      setSelectedIds((prev) => prev.filter((id) => !selectable.includes(id)));
    } else {
      setSelectedIds((prev) => [...new Set([...prev, ...selectable])]);
    }
  };

  const runBatch = async (
    action: "enable" | "disable" | "assign_roles" | "deactivate",
    roleIds?: string[],
  ) => {
    if (selectedIds.length === 0) return;
    const res = await api.batchUsers(selectedIds, action, roleIds);
    setSelectedIds([]);
    const n =
      "deactivated" in res && typeof res.deactivated === "number"
        ? res.deactivated
        : res.processed;
    alert(
      action === "deactivate"
        ? `已删除 ${n} 个用户${res.skipped ? `，跳过 ${res.skipped} 个` : ""}`
        : `已处理 ${n} 个用户${res.skipped ? `，跳过 ${res.skipped} 个` : ""}`,
    );
    await list.reload();
  };

  const onBatchEnable = () => {
    requestConfirm({
      title: "批量启用",
      message: `确定启用选中的 ${selectedIds.length} 个用户？`,
      onConfirm: () => runBatch("enable"),
    });
  };

  const onBatchDisable = () => {
    requestConfirm({
      title: "批量禁用",
      message: `确定禁用选中的 ${selectedIds.length} 个用户？禁用后将强制下线。`,
      destructive: true,
      confirmLabel: "确认禁用",
      onConfirm: () => runBatch("disable"),
    });
  };

  const onOpenBatchRoles = () => {
    setBatchRoleIds(roles[0] ? [roles[0].id] : []);
    setBatchRolesOpen(true);
  };

  const onConfirmBatchRoles = async () => {
    if (batchRoleIds.length === 0) return;
    await runBatch("assign_roles", batchRoleIds);
    setBatchRolesOpen(false);
  };

  const onBatchDeactivate = () => {
    if (selectedIds.length === 0) return;
    requestConfirm({
      title: "批量删除用户",
      message: `确定删除选中的 ${selectedIds.length} 个用户？此操作不可撤销。`,
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await runBatch("deactivate");
      },
    });
  };

  const onRevokeSessions = (u: TenantUser) => {
    requestConfirm({
      title: "强制下线全部会话",
      message: `将使用户「${u.username}」在所有设备上的登录立即失效。`,
      destructive: true,
      confirmLabel: "确认下线",
      onConfirm: async () => {
        const res = await api.revokeAllUserSessions(u.id);
        alert(`已下线 ${res.revoked} 个会话`);
      },
    });
  };

  return (
    <div className="w-full">
      <PageHeader
        title="用户管理"
        description="管理当前租户下的用户账号与角色分配"
        action={
          <div className="flex items-center gap-2">
            {selectedIds.length > 0 && (
              <>
                <button type="button" className="btn-ghost text-sm" onClick={onBatchEnable}>
                  批量启用
                </button>
                <button type="button" className="btn-ghost text-sm" onClick={onBatchDisable}>
                  批量禁用
                </button>
                <button type="button" className="btn-ghost text-sm" onClick={onOpenBatchRoles}>
                  分配角色
                </button>
                <button type="button" className="btn-ghost text-red-600" onClick={onBatchDeactivate}>
                  批量删除 ({selectedIds.length})
                </button>
              </>
            )}
            <button type="button" className="btn-primary" onClick={openCreate}>
              新建用户
            </button>
          </div>
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
                  <th className="w-10 px-4 py-2">
                    <input
                      type="checkbox"
                      aria-label="全选"
                      onChange={toggleSelectAll}
                      checked={
                        list.items.some((u: TenantUser) => u.id !== currentUser?.id) &&
                        list.items
                          .filter((u: TenantUser) => u.id !== currentUser?.id)
                          .every((u: TenantUser) => selectedIds.includes(u.id))
                      }
                    />
                  </th>
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
                    <td colSpan={6} className="px-4 py-8 text-center text-ink-faint">
                      暂无用户
                    </td>
                  </tr>
                )}
                {list.items.map((u: TenantUser) => (
                  <tr key={u.id}>
                    <td className="px-4 py-3">
                      {u.id !== currentUser?.id && (
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(u.id)}
                          onChange={() => toggleSelect(u.id)}
                          aria-label={`选择 ${u.username}`}
                        />
                      )}
                    </td>
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
                          className="mr-3 text-xs text-ink-muted hover:text-ink"
                          onClick={() => onResetPassword(u)}
                        >
                          重置密码
                        </button>
                      )}
                      {u.is_active && (
                        <button
                          type="button"
                          className="mr-3 text-xs text-ink-muted hover:text-ink"
                          onClick={() => onRevokeSessions(u)}
                        >
                          下线会话
                        </button>
                      )}
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
            onSizeChange={list.setSize}
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

      <ResourceDialog
        open={!!resetUser}
        title="重置密码"
        onClose={() => setResetUser(null)}
        footer={
          <>
            <button type="button" className="btn-ghost" onClick={() => setResetUser(null)}>
              取消
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={resetPassword.length < 6}
              onClick={onConfirmResetPassword}
            >
              确认重置
            </button>
          </>
        }
      >
        <p className="text-sm text-ink-muted">
          为用户 <span className="font-medium text-ink">{resetUser?.username}</span>{" "}
          设置新密码。重置后该用户在所有设备上的登录将失效。
        </p>
        <input
          className="input-field mt-3 w-full"
          placeholder="新密码（至少 6 位）"
          type="password"
          value={resetPassword}
          onChange={(e) => setResetPassword(e.target.value)}
        />
      </ResourceDialog>

      <ResourceDialog
        open={batchRolesOpen}
        title={`批量分配角色（${selectedIds.length} 人）`}
        onClose={() => setBatchRolesOpen(false)}
        footer={
          <>
            <button type="button" className="btn-ghost" onClick={() => setBatchRolesOpen(false)}>
              取消
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={batchRoleIds.length === 0}
              onClick={() => void onConfirmBatchRoles()}
            >
              确认分配
            </button>
          </>
        }
      >
        <p className="mb-3 text-sm text-ink-muted">
          将为选中用户<strong>全量替换</strong>为下列角色（与单用户编辑行为一致）。
        </p>
        <div className="flex flex-wrap gap-3">
          {roles.map((r) => (
            <label key={r.id} className="flex cursor-pointer items-center gap-1 text-sm">
              <input
                type="checkbox"
                checked={batchRoleIds.includes(r.id)}
                onChange={() =>
                  setBatchRoleIds((prev) =>
                    prev.includes(r.id) ? prev.filter((x) => x !== r.id) : [...prev, r.id],
                  )
                }
              />
              {r.name}
            </label>
          ))}
        </div>
      </ResourceDialog>

      {confirmDialog}
    </div>
  );
}
