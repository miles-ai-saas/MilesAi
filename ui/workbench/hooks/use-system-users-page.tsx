"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import type { Role, TenantUser } from "@/lib/types";

export function useSystemUsersPage() {
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
    void api.listAssignableRoles().then(setRoles);
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

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const toggleSelectAll = () => {
    const selectable = list.items.filter((u: TenantUser) => u.id !== currentUser?.id).map((u: TenantUser) => u.id);
    if (selectable.length > 0 && selectable.every((id) => selectedIds.includes(id))) {
      setSelectedIds((prev) => prev.filter((id) => !selectable.includes(id)));
    } else {
      setSelectedIds((prev) => [...new Set([...prev, ...selectable])]);
    }
  };

  const runBatch = async (action: "enable" | "disable" | "assign_roles" | "deactivate", roleIdsArg?: string[]) => {
    if (selectedIds.length === 0) return;
    const res = await api.batchUsers(selectedIds, action, roleIdsArg);
    setSelectedIds([]);
    const n = "deactivated" in res && typeof res.deactivated === "number" ? res.deactivated : res.processed;
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

  const toggleBatchRole = (id: string) => {
    setBatchRoleIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const allSelectableSelected =
    list.items.some((u: TenantUser) => u.id !== currentUser?.id) &&
    list.items.filter((u: TenantUser) => u.id !== currentUser?.id).every((u: TenantUser) => selectedIds.includes(u.id));

  return {
    currentUser,
    list,
    roles,
    selectedIds,
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
    batchRolesOpen,
    setBatchRolesOpen,
    batchRoleIds,
    confirmDialog,
    openCreate,
    openEdit,
    toggleRole,
    onSave,
    onDeactivate,
    onResetPassword,
    onConfirmResetPassword,
    toggleSelect,
    toggleSelectAll,
    allSelectableSelected,
    onBatchEnable,
    onBatchDisable,
    onOpenBatchRoles,
    onConfirmBatchRoles,
    onBatchDeactivate,
    onRevokeSessions,
    toggleBatchRole,
  };
}

export type SystemUsersPageVm = ReturnType<typeof useSystemUsersPage>;
