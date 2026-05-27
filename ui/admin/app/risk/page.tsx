"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  adminApi,
  type IpBlacklist,
  type RateLimitRule,
  type RiskEvent,
} from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export default function RiskPage() {
  const ready = useRequireAdmin();
  const [risks, setRisks] = useState<RiskEvent[]>([]);
  const [ips, setIps] = useState<IpBlacklist[]>([]);
  const [rules, setRules] = useState<RateLimitRule[]>([]);
  const [newIp, setNewIp] = useState("");
  const [ipReason, setIpReason] = useState("");

  const reload = async () => {
    const [r, i, rl] = await Promise.all([
      adminApi.listRiskEvents(),
      adminApi.listIpBlacklist(),
      adminApi.listRateLimits(),
    ]);
    setRisks(r.items);
    setIps(i);
    setRules(rl);
  };

  useEffect(() => {
    if (!ready) return;
    reload();
  }, [ready]);

  return (
    <div className="space-y-8">
      <PageHeader title="风控管理" description="风险事件、IP 黑名单与 API 限流" />

      <section className="card p-4">
        <h2 className="text-sm font-semibold text-ink">风险事件</h2>
        <ul className="mt-3 max-h-64 space-y-2 overflow-y-auto text-sm">
          {risks.length === 0 && <li className="text-ink-faint">暂无风险事件</li>}
          {risks.map((e) => (
            <li key={e.id} className="flex items-center justify-between rounded-lg bg-surface-muted px-3 py-2">
              <span>
                <span className="font-medium">{e.event_type}</span>
                <span className="text-ink-muted"> · {e.severity}</span>
                {e.ip_address && (
                  <span className="text-ink-faint"> · {e.ip_address}</span>
                )}
                <span className="ml-2 text-xs text-ink-faint">
                  {e.created_at.slice(0, 19)}
                </span>
              </span>
              {!e.is_resolved ? (
                <button
                  type="button"
                  className="text-xs text-brand hover:underline"
                  onClick={async () => {
                    await adminApi.resolveRisk(e.id);
                    await reload();
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
              await reload();
            }}
          >
            封禁
          </button>
        </div>
        <ul className="mt-3 space-y-1 text-sm">
          {ips.map((ip) => (
            <li key={ip.id} className="flex justify-between rounded-lg bg-surface-muted px-3 py-2">
              <span>
                {ip.ip_address}
                {ip.reason && <span className="text-ink-faint"> — {ip.reason}</span>}
                {!ip.is_active && <span className="text-amber-600"> (已禁用)</span>}
              </span>
              <button
                type="button"
                className="text-xs text-red-600 hover:underline"
                onClick={async () => {
                  await adminApi.toggleIp(ip.id, !ip.is_active);
                  await reload();
                }}
              >
                {ip.is_active ? "禁用规则" : "启用规则"}
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="card p-4">
        <h2 className="text-sm font-semibold text-ink">限流配置</h2>
        <ul className="mt-3 space-y-2 text-sm">
          {rules.length === 0 && <li className="text-ink-faint">暂无限流规则</li>}
          {rules.map((r) => (
            <li key={r.id} className="rounded-lg bg-surface-muted px-3 py-2">
              <span className="font-medium">{r.name}</span>
              <span className="text-ink-muted">
                {" "}
                — {r.path_pattern} · {r.limit_per_minute}/min
              </span>
              {!r.is_active && <span className="text-amber-600"> (停用)</span>}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
