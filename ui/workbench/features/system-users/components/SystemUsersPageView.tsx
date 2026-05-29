"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { SystemUserBatchRolesDialog } from "@/components/system-users/SystemUserBatchRolesDialog";
import { SystemUserFormDialog } from "@/components/system-users/SystemUserFormDialog";
import { SystemUserResetPasswordDialog } from "@/components/system-users/SystemUserResetPasswordDialog";
import { SystemUsersTable } from "@/components/system-users/SystemUsersTable";
import type { SystemUsersPageVm } from "@/hooks/use-system-users-page";
import { SYSTEM_USERS_PAGE_DESC } from "@/lib/system-users-shared";

export function SystemUsersPageView({ vm }: { vm: SystemUsersPageVm }) {
  const { selectedIds, openCreate, onBatchEnable, onBatchDisable, onOpenBatchRoles, onBatchDeactivate, confirmDialog } = vm;

  return (
    <div className="w-full">
      <PageHeader
        title="用户管理"
        description={SYSTEM_USERS_PAGE_DESC}
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
      <SystemUsersTable vm={vm} />
      <SystemUserFormDialog vm={vm} />
      <SystemUserResetPasswordDialog vm={vm} />
      <SystemUserBatchRolesDialog vm={vm} />
      {confirmDialog}
    </div>
  );
}
