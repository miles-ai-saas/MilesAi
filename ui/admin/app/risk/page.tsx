"use client";

import { useCallback, useState } from "react";
import { ListFooter } from "@/components/list/ListFooter";
import { PageHeader } from "@/components/layout/PageHeader";
import { usePagedList } from "@/hooks/use-paged-list";
import { adminApi } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export default function RiskPage() {
  const ready = useRequireAdmin();
  const [newIp, setNewIp] = useState("");
  const [ipReason, setIpReason] = useState("");

  const events = usePagedList(useCallback((p, s) => adminApi.listRiskEvents(p, s), []), {
    enabled: ready,
  });

  const ips = usePagedList(useCallback((p, s) => adminApi.listIpBlacklist(p, s), []), {
    enabled: ready,
  });

  const rules = usePagedList(useCallback((p, s) => adminApi.listRateLimits(p, s), []), {
    enabled: ready,
  });

  return (
    <div className="space-y-8">
      <PageHeader title="风控管理" description="风险事件、IP 黑名单与 API 限流" />

      <section className="card p-4">
        <h2 className="text-sm font-semibold text-ink">风险事件</h2>
        {events.loading ? (
          <p className="mt-3 text-sm text-ink-muted">加载中…</p>
        ) : (
          <>
            <ul className="admin-data-list mt-3">
              {events.items.length === 0 && <li className="text-ink-faint">暂无风险事件</li>}
              {events.items.map((e) => (
                <li key={e.id} className="admin-data-row flex items-center justify-between gap-2">
                  <span>
                    <span className="cell-primary">{e.event_type}</span>
                    <span className="cell-muted"> · {e.severity}</span>
                    {e.ip_address && <span className="admin-data-meta"> · {e.ip_address}</span>}
                    <span className="admin-data-meta ml-2">{e.created_at.slice(0, 19)}</span>
                  </span>
                  {!e.is_resolved ? (
                    <button
                      type="button"
                      className="text-xs text-brand hover:underline"
                      onClick={async () => {
                        await adminApi.resolveRisk(e.id);
                        await events.reload();
                      }}
                    >
                      标记已处理
                    </button>
                  ) : (
                    <span className="text-xs text-emerald-600">已处理</span>
                  )}
                </li>
              ))}
            </ul>
            <ListFooter
              className="mt-3"
              page={events.page}
              size={events.size}
              total={events.total}
              onPageChange={events.setPage}
              onSizeChange={events.setSize}
            />
          </>
        )}
      </section>

      <section className="card p-4">
        <h2 className="text-sm font-semibold text-ink">IP 黑名单</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          <input
            className="input-field max-w-xs"
            placeholder="IP 地址"
            value={newIp}
            onChange={(e) => setNewIp(e.target.value)}
          />
          <input
            className="input-field max-w-xs"
            placeholder="封禁原因（可选）"
            value={ipReason}
            onChange={(e) => setIpReason(e.target.value)}
          />
          <button
            type="button"
            className="btn-primary"
            onClick={async () => {
              if (!newIp.trim()) return;
              await adminApi.addIp(newIp.trim(), ipReason || undefined);
              setNewIp("");
              setIpReason("");
              await ips.reload();
            }}
          >
            封禁
          </button>
        </div>
        {ips.loading ? (
          <p className="mt-3 text-sm text-ink-muted">加载中…</p>
        ) : (
          <>
            <ul className="admin-data-list mt-3">
              {ips.items.length === 0 && <li className="text-ink-faint">暂无黑名单记录</li>}
              {ips.items.map((ip) => (
                <li key={ip.id} className="admin-data-row flex justify-between gap-2">
                  <span>
                    <span className="cell-mono">{ip.ip_address}</span>
                    {ip.reason && <span className="cell-muted"> — {ip.reason}</span>}
                    {!ip.is_active && <span className="text-amber-600"> (已禁用)</span>}
                  </span>
                  <button
                    type="button"
                    className="text-xs text-red-600 hover:underline"
                    onClick={async () => {
                      await adminApi.toggleIp(ip.id, !ip.is_active);
                      await ips.reload();
                    }}
                  >
                    {ip.is_active ? "禁用规则" : "启用规则"}
                  </button>
                </li>
              ))}
            </ul>
            <ListFooter
              className="mt-3"
              page={ips.page}
              size={ips.size}
              total={ips.total}
              onPageChange={ips.setPage}
              onSizeChange={ips.setSize}
            />
          </>
        )}
      </section>

      <section className="card p-4">
        <h2 className="text-sm font-semibold text-ink">限流配置</h2>
        {rules.loading ? (
          <p className="mt-3 text-sm text-ink-muted">加载中…</p>
        ) : (
          <>
            <ul className="admin-data-list mt-3">
              {rules.items.length === 0 && <li className="text-ink-faint">暂无限流规则</li>}
              {rules.items.map((r) => (
                <li key={r.id} className="admin-data-row">
                  <span className="cell-primary">{r.name}</span>
                  <span className="cell-muted">
                    {" "}
                    — <span className="cell-mono">{r.path_pattern}</span> ·{" "}
                    <span className="cell-numeric">{r.limit_per_minute}/min</span>
                  </span>
                  {!r.is_active && <span className="text-amber-600"> (停用)</span>}
                </li>
              ))}
            </ul>
            <ListFooter
              className="mt-3"
              page={rules.page}
              size={rules.size}
              total={rules.total}
              onPageChange={rules.setPage}
              onSizeChange={rules.setSize}
            />
          </>
        )}
      </section>
    </div>
  );
}
