"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import type { PermissionGroup, Role } from "@/lib/types";

export function useSystemRolesPage() {
  const { ready } = useRequireAuth();
  const [groups, setGroups] = useState<PermissionGroup[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Role | null>(null);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [description, setDescription] = useState("");
  const [selectedPermIds, setSelectedPermIds] = useState<Set<string>>(new Set());

  const list = usePagedList(useCallback((p, s) => api.listRoles(p, s), []), { enabled: ready });
  const { requestConfirm, confirmDialog } = useConfirmAction();

  useEffect(() => {
    if (!ready) return;
    void api.listPermissionGroups().then(setGroups);
  }, [ready]);

  const allPerms = groups.flatMap((g) => g.permissions);

  const openCreate = () => {
    setEditing(null);
    setName("");
    setCode("");
    setDescription("");
    setSelectedPermIds(new Set());
    setDialogOpen(true);
  };

  const openEdit = (role: Role) => {
    setEditing(role);
    setName(role.name);
    setCode(role.code);
    setDescription(role.description ?? "");
    const ids = new Set(allPerms.filter((p) => role.permission_codes.includes(p.code)).map((p) => p.id));
    setSelectedPermIds(ids);
    setDialogOpen(true);
  };

  const togglePerm = (id: string) => {
    setSelectedPermIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const onSave = async () => {
    const permission_ids = Array.from(selectedPermIds);
    if (editing) {
      await api.updateRole(editing.id, { name: name.trim(), description, permission_ids });
    } else {
      if (!name.trim() || !code.trim()) return;
      await api.createRole({
        name: name.trim(),
        code: code.trim(),
        description,
        permission_ids,
      });
    }
    setDialogOpen(false);
    await list.reload();
  };

  const onDelete = (role: Role) => {
    requestConfirm({
      title: "删除角色",
      message: (
        <>
          确定删除角色 <span className="font-medium">{role.name}</span>？
        </>
      ),
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deleteRole(role.id);
        await list.reload();
      },
    });
  };

  return {
    groups,
    list,
    dialogOpen,
    setDialogOpen,
    editing,
    name,
    setName,
    code,
    setCode,
    description,
    setDescription,
    selectedPermIds,
    confirmDialog,
    openCreate,
    openEdit,
    togglePerm,
    onSave,
    onDelete,
  };
}

export type SystemRolesPageVm = ReturnType<typeof useSystemRolesPage>;
