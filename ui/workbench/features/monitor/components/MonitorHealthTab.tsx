"use client";

import type { MonitorMeta } from "@/lib/types";
import { monitorHealthComponentLabel, monitorOverallHealthLabel } from "@/features/monitor/lib/monitor-labels";
import type { MonitorPageVm } from "@/features/monitor/hooks/use-monitor-page";

const MONITOR_PRIMARY_COMPONENT_KEYS = ["postgres", "redis", "vector_store", "object_storage"] as const;

function parseComponentHealth(raw: unknown): { ok: boolean; detail?: string } {
  if (typeof raw === "boolean") {
    return { ok: raw, detail: raw ? undefined : "探测未通过" };
  }
  if (typeof raw === "string") {
    const ok = raw === "healthy" || raw === "ok" || raw === "up";
    return { ok, detail: ok ? undefined : raw };
  }
  if (raw && typeof raw === "object") {
    const item = raw as Record<string, unknown>;
    if (typeof item.healthy === "boolean") {
      return {
        ok: item.healthy,
        detail: item.message ? String(item.message) : item.error ? String(item.error) : undefined,
      };
    }
    const status = typeof item.status === "string" ? item.status : undefined;
    const ok = status === "healthy" || status === "ok" || status === "up";
    return {
      ok,
      detail: item.message ? String(item.message) : item.error ? String(item.error) : status,
    };
  }
  return { ok: false, detail: "未知状态" };
}

function selectPrimaryComponents(components: Record<string, unknown>) {
  return MONITOR_PRIMARY_COMPONENT_KEYS.filter((k) => k in components).map((k) => [k, components[k]] as const);
}

function HealthStatusBadge({ ok, status, monitorMeta }: { ok: boolean; status?: string; monitorMeta: MonitorMeta | null }) {
  const label = monitorOverallHealthLabel(status, ok, monitorMeta);
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${
        ok ? "bg-emerald-50 text-emerald-800 ring-emerald-200" : "bg-amber-50 text-amber-800 ring-amber-200"
      }`}
    >
      {label}
    </span>
  );
}

function HealthComponents({ components, monitorMeta }: { components: Record<string, unknown>; monitorMeta: MonitorMeta | null }) {
  const entries = selectPrimaryComponents(components);
  if (entries.length === 0) {
    return <p className="text-sm text-ink-faint">暂无组件探测数据</p>;
  }
  return (
    <ul className="space-y-2">
      {entries.map(([name, raw]) => {
        const { ok, detail } = parseComponentHealth(raw);
        return (
          <li
            key={name}
            className="flex flex-col gap-2 rounded-lg border border-line-soft bg-surface-muted px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0">
              <p className="font-medium text-ink">{monitorHealthComponentLabel(name, monitorMeta)}</p>
              {detail && <p className="mt-1 text-xs text-ink-muted line-clamp-2">{detail}</p>}
            </div>
            <HealthStatusBadge ok={ok} monitorMeta={monitorMeta} />
          </li>
        );
      })}
    </ul>
  );
}

export function MonitorHealthTab({ vm }: { vm: MonitorPageVm }) {
  const { health, monitorMeta, redisInfo, workerInfo } = vm;
  if (!health) return null;
  const components = health?.components ?? {};

  return (
    <div className="col-span-full mx-auto w-full max-w-3xl space-y-4">
      <section className="rounded-xl border border-line bg-surface p-5 shadow-panel">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-ink">整体状态</h2>
            <p className="mt-1 text-sm text-ink-muted">数据库、向量库、消息队列等依赖探测结果</p>
          </div>
          <HealthStatusBadge ok={health?.healthy ?? health?.status === "healthy"} status={health?.status} monitorMeta={monitorMeta} />
        </div>
      </section>
      <section className="rounded-xl border border-line bg-surface p-5 shadow-panel">
        <h3 className="text-sm font-semibold text-ink">组件明细</h3>
        <div className="mt-4">
          <HealthComponents components={components} monitorMeta={monitorMeta} />
        </div>
      </section>
      {redisInfo && !("error" in redisInfo) && (
        <section className="rounded-xl border border-line bg-surface p-5 shadow-panel">
          <h3 className="text-sm font-semibold text-ink">Redis 缓存</h3>
          <div className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div className="rounded-lg bg-surface-muted p-3">
              <p className="text-xs text-ink-faint">版本</p>
              <p className="font-mono font-medium">{String(redisInfo.redis_version ?? "N/A")}</p>
            </div>
            <div className="rounded-lg bg-surface-muted p-3">
              <p className="text-xs text-ink-faint">命中率</p>
              <p className="font-mono font-medium text-brand">{String(redisInfo.hit_rate ?? 0)}%</p>
            </div>
            <div className="rounded-lg bg-surface-muted p-3">
              <p className="text-xs text-ink-faint">内存使用</p>
              <p className="font-mono font-medium">{String(redisInfo.used_memory_human ?? "N/A")}</p>
            </div>
            <div className="rounded-lg bg-surface-muted p-3">
              <p className="text-xs text-ink-faint">运行时长</p>
              <p className="font-mono font-medium">{Math.floor(Number(redisInfo.uptime_in_seconds ?? 0) / 3600)}h</p>
            </div>
          </div>
        </section>
      )}
      {workerInfo && !("error" in workerInfo) && (
        <section className="rounded-xl border border-line bg-surface p-5 shadow-panel">
          <h3 className="text-sm font-semibold text-ink">Celery Worker</h3>
          <div className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div className="rounded-lg bg-surface-muted p-3">
              <p className="text-xs text-ink-faint">Worker 数</p>
              <p className="font-mono font-medium text-brand">{String(workerInfo.worker_count ?? 0)}</p>
            </div>
            <div className="rounded-lg bg-surface-muted p-3">
              <p className="text-xs text-ink-faint">活跃任务</p>
              <p className="font-mono font-medium">{String(workerInfo.total_active_tasks ?? 0)}</p>
            </div>
            <div className="rounded-lg bg-surface-muted p-3">
              <p className="text-xs text-ink-faint">预留任务</p>
              <p className="font-mono font-medium">{String(workerInfo.total_reserved_tasks ?? 0)}</p>
            </div>
            <div className="rounded-lg bg-surface-muted p-3">
              <p className="text-xs text-ink-faint">定时任务</p>
              <p className="font-mono font-medium">{String(workerInfo.total_scheduled ?? 0)}</p>
            </div>
          </div>
          {Array.isArray(workerInfo.workers) && (workerInfo.workers as Record<string, unknown>[]).length > 0 && (
            <div className="mt-4 overflow-auto rounded-lg border border-line-soft bg-surface-muted p-3">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-ink-faint">
                    <th className="px-2 py-1">Worker</th>
                    <th className="px-2 py-1">并发</th>
                    <th className="px-2 py-1">活跃</th>
                    <th className="px-2 py-1">预留</th>
                    <th className="px-2 py-1">队列</th>
                  </tr>
                </thead>
                <tbody>
                  {(workerInfo.workers as Record<string, unknown>[]).map((w: Record<string, unknown>, i: number) => (
                    <tr key={i} className="border-t border-line-soft">
                      <td className="px-2 py-1 font-mono">{String(w.name ?? "").split("@")[0]}</td>
                      <td className="px-2 py-1 tabular-nums">{String(w.pool_size ?? "-")}</td>
                      <td className="px-2 py-1 tabular-nums">{String(w.active_tasks ?? 0)}</td>
                      <td className="px-2 py-1 tabular-nums">{String(w.reserved_tasks ?? 0)}</td>
                      <td className="px-2 py-1 tabular-nums text-ink-faint">{Array.isArray(w.queues) ? (w.queues as string[]).join(", ") : "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
