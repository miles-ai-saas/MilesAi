"use client";

import type { ReactNode } from "react";
import { PageMessage } from "@/components/ui/PageMessage";
import { StatChip } from "@/components/ui/StatChip";
import type { MonitorMeta } from "@/lib/types";
import { monitorHealthComponentLabel, monitorOverallHealthLabel } from "@/features/monitor/lib/monitor-labels";

export { StatChip, PageMessage };

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

export function ChartPanel({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-line bg-surface p-5 shadow-card">
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      {subtitle && <p className="mt-1 text-xs text-ink-muted">{subtitle}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function HealthStatusBadge({ ok, status, monitorMeta }: { ok: boolean; status?: string; monitorMeta: MonitorMeta | null }) {
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

export function HealthComponents({ components, monitorMeta }: { components: Record<string, unknown>; monitorMeta: MonitorMeta | null }) {
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
