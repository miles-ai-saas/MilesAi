"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { PageHeader } from "@/components/layout/PageHeader";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import type { PermissionGroup, Role } from "@/lib/types";

export default function SystemRolesPage() {
  const { ready } = useRequireAuth();
  const [groups, setGroups] = useState<PermissionGroup[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Role | null>(null);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [description, setDescription] = useState("");
  const [selectedPermIds, setSelectedPermIds] = useState<Set<string>>(new Set());

  const list = usePagedList(useCallback((p, s) => api.listRoles(p, s), []), { enabled: ready });

  useEffect(() => {
    if (!ready) return;
    api.listPermissionGroups().then(setGroups);
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
    const ids = new Set(
      allPerms.filter((p) => role.permission_codes.includes(p.code)).map((p) => p.id),
    );
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

  const onDelete = async (role: Role) => {
    if (!confirm(`确定删除角色「${role.name}」？`)) return;
    await api.deleteRole(role.id);
    await list.reload();
  };

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title="角色权限"
        description="为本租户配置角色与权限，用户通过角色获得访问能力。"
        action={
          <button type="button" className="btn-primary" onClick={openCreate}>
            新建角色
          </button>
        }
      />

      {list.loading ? (
        <p className="text-sm text-ink-muted">加载中…</p>
      ) : (
        <>
          <div className="resource-card-grid">
            {list.items.map((role) => (
              <ResourceItemCard
                key={role.id}
                title={role.name}
                description={role.description ?? role.code}
                badge={role.is_system ? "系统" : `${role.permission_codes.length} 项权限`}
                meta={
                  <span className="line-clamp-2 text-xs">
                    {role.permission_codes.slice(0, 6).join(" · ")}
                    {role.permission_codes.length > 6 ? " …" : ""}
                  </span>
                }
                actions={
                  role.is_system || role.tenant_id == null ? (
                    <span className="text-xs text-ink-faint">内置角色不可编辑</span>
                  ) : (
                    <CardActions onEdit={() => openEdit(role)} onDelete={() => onDelete(role)} />
                  )
                }
              />
            ))}
          </div>
          <ResourceListFooter
            className="mt-4"
            page={list.page}
            size={list.size}
            total={list.total}
            onPageChange={list.setPage}
          />
        </>
      )}

      <ResourceDialog
        open={dialogOpen}
        title={editing ? "编辑角色" : "新建角色"}
        onClose={() => setDialogOpen(false)}
        footer={
          <>
            <button type="button" className="btn-ghost" onClick={() => setDialogOpen(false)}>
              取消
            </button>
            <button type="button" className="btn-primary" onClick={onSave}>
              保存
            </button>
          </>
        }
      >
        <input
          className="input-field w-full"
          placeholder="角色名称"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        {!editing && (
          <input
            className="input-field w-full"
            placeholder="角色编码（英文）"
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        )}
        <input
          className="input-field w-full"
          placeholder="描述（可选）"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <div className="max-h-64 overflow-y-auto rounded border border-line-soft p-3">
          <p className="mb-2 text-xs font-medium text-ink-muted">权限</p>
          {groups.map((g) => (
            <div key={g.module} className="mb-3">
              <p className="mb-1 text-xs font-semibold text-ink">{g.module}</p>
              <div className="flex flex-wrap gap-2">
                {g.permissions.map((p) => (
                  <label key={p.id} className="flex cursor-pointer items-center gap-1 text-xs">
                    <input
                      type="checkbox"
                      checked={selectedPermIds.has(p.id)}
                      onChange={() => togglePerm(p.id)}
                    />
                    {p.name}
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>
      </ResourceDialog>
    </div>
  );
}
