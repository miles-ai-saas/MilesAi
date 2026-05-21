"use client";

import { useEffect, useState } from "react";
import { adminApi, type AuditLog, type IpBlacklist, type RateLimitRule, type RiskEvent } from "@/lib/admin-api";
import { useRequireAdmin } from "@/lib/admin-auth-store";

export default function AdminRiskPage() {
  const ready = useRequireAdmin();
  const [risks, setRisks] = useState<RiskEvent[]>([]);
  const [ips, setIps] = useState<IpBlacklist[]>([]);
  const [rules, setRules] = useState<RateLimitRule[]>([]);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [newIp, setNewIp] = useState("");

  const reload = async () => {
    const [r, i, rl, l] = await Promise.all([
      adminApi.listRiskEvents(),
      adminApi.listIpBlacklist(),
      adminApi.listRateLimits(),
      adminApi.listAuditLogs(),
    ]);
    setRisks(r.items);
    setIps(i);
    setRules(rl);
    setLogs(l.items);
  };

  useEffect(() => {
    if (!ready) return;
    reload();
  }, [ready]);

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-bold">风控管理</h1>

      <section className="rounded-lg border bg-white p-4">
        <h2 className="text-sm font-semibold">风险事件</h2>
        <ul className="mt-3 max-h-40 space-y-2 overflow-y-auto text-sm">
          {risks.length === 0 && <li className="text-slate-400">暂无</li>}
          {risks.map((e) => (
            <li key={e.id} className="flex justify-between rounded bg-slate-50 px-3 py-2">
              <span>
                {e.event_type} · {e.severity} · {e.ip_address || "-"}
              </span>
              {!e.is_resolved && (
                <button
                  type="button"
                  className="text-xs text-brand"
                  onClick={async () => {
                    await adminApi.resolveRisk(e.id);
                    await reload();
                  }}
                >
                  标记已处理
                </button>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-lg border bg-white p-4">
        <h2 className="text-sm font-semibold">IP 黑名单</h2>
        <div className="mt-2 flex gap-2">
          <input
            className="rounded border px-3 py-2 text-sm"
            placeholder="IP 地址"
            value={newIp}
            onChange={(e) => setNewIp(e.target.value)}
          />
          <button
            type="button"
            className="rounded bg-brand px-4 py-2 text-sm text-white"
            onClick={async () => {
              await adminApi.addIp(newIp);
              setNewIp("");
              await reload();
            }}
          >
            封禁
          </button>
        </div>
        <ul className="mt-3 space-y-1 text-sm">
          {ips.map((ip) => (
            <li key={ip.id} className="flex justify-between rounded bg-slate-50 px-3 py-2">
              <span>
                {ip.ip_address} {ip.is_active ? "" : "(已禁用)"}
              </span>
              <button
                type="button"
                className="text-xs text-red-600"
                onClick={async () => {
                  await adminApi.toggleIp(ip.id, !ip.is_active);
                  await reload();
                }}
              >
                {ip.is_active ? "禁用" : "启用"}
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-lg border bg-white p-4">
        <h2 className="text-sm font-semibold">限流配置</h2>
        <ul className="mt-3 space-y-2 text-sm">
          {rules.map((r) => (
            <li key={r.id} className="rounded bg-slate-50 px-3 py-2">
              {r.name}: {r.path_pattern} — {r.limit_per_minute}/min
              {r.is_active ? "" : " (停用)"}
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-lg border bg-white p-4">
        <h2 className="text-sm font-semibold">审计日志</h2>
        <ul className="mt-3 max-h-64 space-y-1 overflow-y-auto text-xs text-slate-600">
          {logs.map((l) => (
            <li key={l.id} className="rounded bg-slate-50 px-2 py-1">
              [{l.created_at.slice(0, 19)}] {l.action}
              {l.ip_address && ` · ${l.ip_address}`}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
