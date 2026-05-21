"use client";

import { useCallback } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { PageHeader } from "@/components/layout/PageHeader";
import type { TenantUser } from "@/lib/types";

export default function SystemUsersPage() {
  const { ready } = useRequireAuth();
  const list = usePagedList(useCallback((p, s) => api.listUsers(p, s), []), { enabled: ready });

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title="用户管理" description="管理当前租户下的用户账号与角色" />
      {list.loading ? (
        <p className="text-sm text-ink-muted">加载中…</p>
      ) : (
        <>
          <div className="card overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line bg-surface-muted text-xs text-ink-muted">
                <tr>
                  <th className="px-4 py-2">用户名</th>
                  <th className="px-4 py-2">邮箱</th>
                  <th className="px-4 py-2">状态</th>
                  <th className="px-4 py-2">角色</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line-soft">
                {list.items.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-ink-faint">
                      暂无用户
                    </td>
                  </tr>
                )}
                {list.items.map((u: TenantUser) => (
                  <tr key={u.id}>
                    <td className="px-4 py-3 font-medium text-ink">{u.username}</td>
                    <td className="px-4 py-3 text-ink-muted">{u.email}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded px-2 py-0.5 text-xs ${
                          u.is_active ? "bg-brand-light text-brand" : "bg-surface-muted text-ink-faint"
                        }`}
                      >
                        {u.is_active ? "启用" : "禁用"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-ink-muted">
                      {u.role_codes?.join(", ") || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ResourceListFooter
            className="mt-3"
            page={list.page}
            size={list.size}
            total={list.total}
            onPageChange={list.setPage}
          />
        </>
      )}
    </div>
  );
}
