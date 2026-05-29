"use client";

import { HealthComponents, HealthStatusBadge } from "@/features/monitor/components/monitor-page-ui";
import type { MonitorPageVm } from "@/features/monitor/hooks/use-monitor-page";

export function MonitorHealthTab({ vm }: { vm: MonitorPageVm }) {
  const { health, monitorMeta, redisInfo, workerInfo } = vm;
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
          {health ? <HealthComponents components={components} monitorMeta={monitorMeta} /> : <p className="text-sm text-ink-muted">加载中…</p>}
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
