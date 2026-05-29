"use client";

import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import type { SystemUsersPageVm } from "@/features/system-users/hooks/use-system-users-page";
import type { TenantUser } from "@/lib/types";

export function SystemUsersTable({ vm }: { vm: SystemUsersPageVm }) {
  const {
    currentUser,
    list,
    selectedIds,
    allSelectableSelected,
    toggleSelectAll,
    toggleSelect,
    openEdit,
    onResetPassword,
    onRevokeSessions,
    onDeactivate,
  } = vm;

  if (list.loading) {
    return <p className="text-sm text-ink-muted">加载中…</p>;
  }

  return (
    <>
      <div className="card overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-line bg-surface-muted text-xs text-ink-muted">
            <tr>
              <th className="w-10 px-4 py-2">
                <input type="checkbox" aria-label="全选" onChange={toggleSelectAll} checked={allSelectableSelected} />
              </th>
              <th className="px-4 py-2">用户名</th>
              <th className="px-4 py-2">邮箱</th>
              <th className="px-4 py-2">状态</th>
              <th className="px-4 py-2">角色</th>
              <th className="px-4 py-2 text-right">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line-soft">
            {list.items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-ink-faint">
                  暂无用户
                </td>
              </tr>
            )}
            {list.items.map((u: TenantUser) => (
              <tr key={u.id}>
                <td className="px-4 py-3">
                  {u.id !== currentUser?.id && (
                    <input type="checkbox" checked={selectedIds.includes(u.id)} onChange={() => toggleSelect(u.id)} aria-label={`选择 ${u.username}`} />
                  )}
                </td>
                <td className="px-4 py-3 font-medium text-ink">{u.username}</td>
                <td className="px-4 py-3 text-ink-muted">{u.email}</td>
                <td className="px-4 py-3">
                  <span className={`rounded px-2 py-0.5 text-xs ${u.is_active ? "bg-brand-light text-brand" : "bg-surface-muted text-ink-faint"}`}>
                    {u.is_active ? "启用" : "禁用"}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-ink-muted">{u.role_codes?.join(", ") || "—"}</td>
                <td className="px-4 py-3 text-right">
                  <button type="button" className="mr-3 text-xs text-brand hover:underline" onClick={() => openEdit(u)}>
                    编辑
                  </button>
                  {u.is_active && (
                    <button type="button" className="mr-3 text-xs text-ink-muted hover:text-ink" onClick={() => onResetPassword(u)}>
                      重置密码
                    </button>
                  )}
                  {u.is_active && (
                    <button type="button" className="mr-3 text-xs text-ink-muted hover:text-ink" onClick={() => onRevokeSessions(u)}>
                      下线会话
                    </button>
                  )}
                  {u.is_active && (
                    <button type="button" className="text-xs text-red-600 hover:underline" onClick={() => onDeactivate(u)}>
                      删除
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ResourceListFooter className="mt-3" page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
    </>
  );
}
