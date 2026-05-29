"use client";

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import type { SystemRolesPageVm } from "@/hooks/use-system-roles-page";

export function SystemRoleFormDialog({ vm }: { vm: SystemRolesPageVm }) {
  const {
    groups,
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
    togglePerm,
    onSave,
  } = vm;

  return (
    <ResourceDialog
      open={dialogOpen}
      title={editing ? "编辑角色" : "新建角色"}
      onClose={() => setDialogOpen(false)}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={() => setDialogOpen(false)}>
            取消
          </button>
          <button type="button" className="btn-primary" onClick={() => void onSave()}>
            保存
          </button>
        </>
      }
    >
      <input className="input-field w-full" placeholder="角色名称" value={name} onChange={(e) => setName(e.target.value)} />
      {!editing && <input className="input-field w-full" placeholder="角色编码（英文）" value={code} onChange={(e) => setCode(e.target.value)} />}
      <input className="input-field w-full" placeholder="描述（可选）" value={description} onChange={(e) => setDescription(e.target.value)} />
      <div className="max-h-64 overflow-y-auto rounded border border-line-soft p-3">
        <p className="mb-2 text-xs font-medium text-ink-muted">权限</p>
        {groups.map((g) => (
          <div key={g.module} className="mb-3">
            <p className="mb-1 text-xs font-semibold text-ink">{g.module}</p>
            <div className="flex flex-wrap gap-2">
              {g.permissions.map((p) => (
                <label key={p.id} className="flex cursor-pointer items-center gap-1 text-xs">
                  <input type="checkbox" checked={selectedPermIds.has(p.id)} onChange={() => togglePerm(p.id)} />
                  {p.name}
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>
    </ResourceDialog>
  );
}
