"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { adminApi, type AuditLog } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export default function AuditPage() {
  const ready = useRequireAdmin();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    if (!ready) return;
    adminApi.listAuditLogs().then((res) => setLogs(res.items));
  }, [ready]);

  const filtered = filter.trim()
    ? logs.filter(
        (l) =>
          l.action.includes(filter) ||
          l.ip_address?.includes(filter) ||
          l.tenant_id?.includes(filter),
      )
    : logs;

  return (
    <div>
      <PageHeader title="审计日志" description="平台级操作与敏感行为记录" />

      <div className="mb-4">
        <input
          className="input-field max-w-md"
          placeholder="按 action / IP / 租户 ID 筛选"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </div>

      <section className="card p-4">
        <ul className="max-h-[32rem] space-y-2 overflow-y-auto text-sm">
          {filtered.length === 0 && (
            <li className="text-ink-faint">暂无审计记录</li>
          )}
          {filtered.map((l) => (
            <li key={l.id} className="rounded-lg border border-line-soft bg-surface-muted px-3 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs text-ink-faint">
                  {l.created_at.slice(0, 19)}
                </span>
                <span className="font-medium text-ink">{l.action}</span>
                {l.tenant_id && (
                  <span className="badge bg-brand/10 text-brand">
                    租户 {l.tenant_id.slice(0, 8)}…
                  </span>
                )}
                {l.ip_address && (
                  <span className="text-xs text-ink-muted">{l.ip_address}</span>
                )}
              </div>
              {Object.keys(l.detail || {}).length > 0 && (
                <pre className="mt-1 overflow-x-auto text-xs text-ink-muted">
                  {JSON.stringify(l.detail, null, 2)}
                </pre>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
