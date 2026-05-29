/** 监控页 Tab、健康探测解析等共享常量。 */

export type MonitorTab = "overview" | "trends" | "usage" | "health" | "alerts";

export const MONITOR_MAIN_TABS: { key: MonitorTab; label: string }[] = [
  { key: "overview", label: "概览" },
  { key: "trends", label: "趋势分析" },
  { key: "usage", label: "模型用量" },
  { key: "health", label: "系统健康" },
  { key: "alerts", label: "告警配置" },
];

/** 与后端 collect_health_status 主键一致 */
export const MONITOR_PRIMARY_COMPONENT_KEYS = ["postgres", "redis", "vector_store", "object_storage"] as const;

export type MonitorHealthPayload = {
  healthy?: boolean;
  status?: string;
  components?: Record<string, unknown>;
};

export function parseComponentHealth(raw: unknown): { ok: boolean; detail?: string } {
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

export function selectPrimaryComponents(components: Record<string, unknown>) {
  return MONITOR_PRIMARY_COMPONENT_KEYS.filter((k) => k in components).map((k) => [k, components[k]] as const);
}
