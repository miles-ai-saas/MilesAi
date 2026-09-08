"use client";

import { ListFooter } from "@/components/list/ListFooter";
import type { RiskPageVm } from "@/features/risk/hooks/use-risk-page";

export function RiskIpBlacklistSection({ vm }: { vm: RiskPageVm }) {
  const { ips, newIp, setNewIp, ipReason, setIpReason, onAddIp, onToggleIp } = vm;

  return (
    <section className="card p-4">
      <h2 className="text-sm font-semibold text-ink">IP 黑名单</h2>
      <div className="mt-3 flex flex-wrap gap-2">
        <input className="input-field max-w-xs" placeholder="IP 地址" value={newIp} onChange={(e) => setNewIp(e.target.value)} />
        <input className="input-field max-w-xs" placeholder="封禁原因（可选）" value={ipReason} onChange={(e) => setIpReason(e.target.value)} />
        <button type="button" className="btn-primary" onClick={() => void onAddIp()}>
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
                <button type="button" className="text-xs text-red-600 hover:underline" onClick={() => void onToggleIp(ip.id, !ip.is_active)}>
                  {ip.is_active ? "禁用规则" : "启用规则"}
                </button>
              </li>
            ))}
          </ul>
          <ListFooter className="mt-3" page={ips.page} size={ips.size} total={ips.total} onPageChange={ips.setPage} onSizeChange={ips.setSize} />
        </>
      )}
    </section>
  );
}
