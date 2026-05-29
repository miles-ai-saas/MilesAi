"use client";

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import type { SystemUsersPageVm } from "@/features/system-users/hooks/use-system-users-page";

export function SystemUserBatchRolesDialog({ vm }: { vm: SystemUsersPageVm }) {
  const { batchRolesOpen, setBatchRolesOpen, selectedIds, batchRoleIds, roles, toggleBatchRole, onConfirmBatchRoles } = vm;

  return (
    <ResourceDialog
      open={batchRolesOpen}
      title={`批量分配角色（${selectedIds.length} 人）`}
      onClose={() => setBatchRolesOpen(false)}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={() => setBatchRolesOpen(false)}>
            取消
          </button>
          <button type="button" className="btn-primary" disabled={batchRoleIds.length === 0} onClick={() => void onConfirmBatchRoles()}>
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
            <input type="checkbox" checked={batchRoleIds.includes(r.id)} onChange={() => toggleBatchRole(r.id)} />
            {r.name}
          </label>
        ))}
      </div>
    </ResourceDialog>
  );
}
