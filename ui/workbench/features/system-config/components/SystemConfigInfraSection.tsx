"use client";

import { INFRA_PREVIEW_LABELS, infraStatusClass, infraStatusLabel } from "@/features/system-config/lib/system-config-shared";
import type { SystemConfigPageVm } from "@/features/system-config/hooks/use-system-config-page";

export function SystemConfigInfraSection({ vm }: { vm: SystemConfigPageVm }) {
  const { user, infra, testing, testingId, onTestAll, onTestOne } = vm;
  if (!infra) return null;

  return (
    <section className="card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-ink">基础设施</h2>
          <p className="mt-0.5 text-xs text-ink-muted">部署级连接信息（脱敏）；修改请通过运维配置 .env / K8s Secret</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`rounded px-2 py-0.5 text-xs ${infra.healthy ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-800"}`}>
            {infra.healthy ? "全部正常" : "部分异常"}
          </span>
          {user?.is_superuser && (
            <button type="button" className="btn-ghost text-sm" disabled={testing} onClick={() => void onTestAll()}>
              {testing && !testingId ? "测试中…" : "测试全部连接"}
            </button>
          )}
        </div>
      </div>

      <div className="mt-4 overflow-hidden rounded border border-line-soft">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-line bg-surface-muted text-xs text-ink-muted">
            <tr>
              <th className="px-3 py-2">组件</th>
              <th className="px-3 py-2">状态</th>
              <th className="px-3 py-2">耗时</th>
              {user?.is_superuser && <th className="px-3 py-2 text-right">操作</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-line-soft">
            {infra.components.map((c) => (
              <tr key={c.id}>
                <td className="px-3 py-2">
                  <span className="font-medium text-ink">{c.label}</span>
                  {c.message && <p className="mt-0.5 text-xs text-ink-faint">{c.message}</p>}
                </td>
                <td className="px-3 py-2">
                  <span className={`rounded px-2 py-0.5 text-xs ${infraStatusClass(c.status)}`}>{infraStatusLabel(c.status)}</span>
                </td>
                <td className="px-3 py-2 tabular-nums text-xs text-ink-muted">{c.latency_ms != null ? `${c.latency_ms} ms` : "—"}</td>
                {user?.is_superuser && (
                  <td className="px-3 py-2 text-right">
                    <button
                      type="button"
                      className="text-xs text-brand hover:underline disabled:opacity-50"
                      disabled={testing}
                      onClick={() => void onTestOne(c.id)}
                    >
                      {testing && testingId === c.id ? "测试中…" : "测试"}
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 className="mt-4 text-xs font-medium text-ink-muted">连接配置（脱敏）</h3>
      <ul className="mt-2 space-y-1 text-xs text-ink-muted">
        {Object.entries(infra.settings_preview).map(([k, v]) => (
          <li key={k}>
            <span className="text-ink-faint">{INFRA_PREVIEW_LABELS[k] ?? k}:</span> {String(v ?? "—")}
          </li>
        ))}
      </ul>
    </section>
  );
}
