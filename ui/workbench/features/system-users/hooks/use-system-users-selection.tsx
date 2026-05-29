"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Role, TenantUser } from "@/lib/types";
import type { useSystemUsersList } from "@/hooks/use-system-users-list";
import type { useConfirmAction } from "@/hooks/use-confirm-action";

type ListSlice = ReturnType<typeof useSystemUsersList>;

export function useSystemUsersSelection(
  { currentUser, list, roles }: ListSlice,
  requestConfirm: ReturnType<typeof useConfirmAction>["requestConfirm"],
) {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [batchRolesOpen, setBatchRolesOpen] = useState(false);
  const [batchRoleIds, setBatchRoleIds] = useState<string[]>([]);

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
    selectedIds,
    batchRolesOpen,
    setBatchRolesOpen,
    batchRoleIds,
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
