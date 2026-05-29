"use client";

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import type { SystemUsersPageVm } from "@/features/system-users/hooks/use-system-users-page";

export function SystemUserFormDialog({ vm }: { vm: SystemUsersPageVm }) {
  const {
    createOpen,
    setCreateOpen,
    editUser,
    username,
    setUsername,
    email,
    setEmail,
    password,
    setPassword,
    phone,
    setPhone,
    isActive,
    setIsActive,
    roleIds,
    roles,
    toggleRole,
    onSave,
  } = vm;

  return (
    <ResourceDialog
      open={createOpen}
      title={editUser ? "编辑用户" : "新建用户"}
      onClose={() => setCreateOpen(false)}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={() => setCreateOpen(false)}>
            取消
          </button>
          <button type="button" className="btn-primary" onClick={() => void onSave()}>
            保存
          </button>
        </>
      }
    >
      {!editUser && <input className="input-field w-full" placeholder="用户名" value={username} onChange={(e) => setUsername(e.target.value)} />}
      <input className="input-field w-full" placeholder="邮箱" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      {!editUser && (
        <input className="input-field w-full" placeholder="密码（至少 6 位）" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
      )}
      <input className="input-field w-full" placeholder="手机号（可选）" value={phone} onChange={(e) => setPhone(e.target.value)} />
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
              <input type="checkbox" checked={roleIds.includes(r.id)} onChange={() => toggleRole(r.id)} />
              {r.name}
            </label>
          ))}
        </div>
      </div>
    </ResourceDialog>
  );
}
