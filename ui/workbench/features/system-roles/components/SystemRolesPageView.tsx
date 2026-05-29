"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { SystemRoleFormDialog } from "@/features/system-roles/components/SystemRoleFormDialog";
import { SystemRolesCatalog } from "@/features/system-roles/components/SystemRolesCatalog";
import type { SystemRolesPageVm } from "@/features/system-roles/hooks/use-system-roles-page";

const SYSTEM_ROLES_PAGE_DESC = "为本租户配置角色与权限，用户通过角色获得访问能力。";

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
