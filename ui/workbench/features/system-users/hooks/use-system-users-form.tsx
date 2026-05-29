"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { TenantUser } from "@/lib/types";
import type { useSystemUsersList } from "@/hooks/use-system-users-list";
import type { useConfirmAction } from "@/hooks/use-confirm-action";

type ListSlice = ReturnType<typeof useSystemUsersList>;

export function useSystemUsersForm(
  { list, roles }: ListSlice,
  requestConfirm: ReturnType<typeof useConfirmAction>["requestConfirm"],
) {
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
    setRoleIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
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

  return {
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
    resetUser,
    setResetUser,
    resetPassword,
    setResetPassword,
    openCreate,
    openEdit,
    toggleRole,
    onSave,
    onDeactivate,
    onResetPassword,
    onConfirmResetPassword,
  };
}
