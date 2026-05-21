"use client";

import { useCallback } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { PageHeader } from "@/components/layout/PageHeader";
import type { TenantAuditLog } from "@/lib/types";

export default function SystemAuditPage() {
  const { ready } = useRequireAuth();
  const list = usePagedList(useCallback((p, s) => api.listAuditLogs(p, s), []), { enabled: ready });

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title="审计日志" description="记录租户内关键操作行为" />
      {list.loading ? (
        <p className="text-sm text-ink-muted">加载中…</p>
      ) : (
        <>
          <ul className="card divide-y text-sm">
            {list.items.length === 0 && (
              <li className="px-4 py-8 text-center text-ink-faint">暂无审计记录</li>
            )}
            {list.items.map((log: TenantAuditLog) => (
              <li key={log.id} className="px-4 py-3">
                <div className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
                  <span>{log.created_at.slice(0, 19).replace("T", " ")}</span>
                  <span className="font-medium text-brand">{log.action}</span>
                  {log.resource_type && (
                    <span>
                      {log.resource_type}
                      {log.resource_id ? ` · ${log.resource_id.slice(0, 8)}…` : ""}
                    </span>
                  )}
                </div>
                {log.ip_address && <p className="mt-1 text-xs text-ink-faint">IP {log.ip_address}</p>}
              </li>
            ))}
          </ul>
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
