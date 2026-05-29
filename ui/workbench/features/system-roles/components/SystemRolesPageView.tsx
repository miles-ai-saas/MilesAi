"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { SystemRoleFormDialog } from "@/components/system-roles/SystemRoleFormDialog";
import { SystemRolesCatalog } from "@/components/system-roles/SystemRolesCatalog";
import type { SystemRolesPageVm } from "@/hooks/use-system-roles-page";
import { SYSTEM_ROLES_PAGE_DESC } from "@/lib/system-roles-shared";

export function SystemRolesPageView({ vm }: { vm: SystemRolesPageVm }) {
  const { openCreate, confirmDialog } = vm;

  return (
    <div className="w-full">
      <PageHeader
        title="角色权限"
        description={SYSTEM_ROLES_PAGE_DESC}
        action={
          <button type="button" className="btn-primary" onClick={openCreate}>
            新建角色
          </button>
        }
      />
      <SystemRolesCatalog vm={vm} />
      <SystemRoleFormDialog vm={vm} />
      {confirmDialog}
    </div>
  );
}
