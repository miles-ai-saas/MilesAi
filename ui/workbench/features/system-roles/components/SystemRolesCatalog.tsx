"use client";

import { CardActions } from "@/components/resource/CardActions";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import type { SystemRolesPageVm } from "@/features/system-roles/hooks/use-system-roles-page";

export function SystemRolesCatalog({ vm }: { vm: SystemRolesPageVm }) {
  const { list, openEdit, onDelete } = vm;

  if (list.loading) {
    return <p className="text-sm text-ink-muted">加载中…</p>;
  }

  return (
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
      <ResourceListFooter className="mt-4" page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
    </>
  );
}
