import type { MonitorTrends, MonitorStats, MonitorReport, AlertConfig } from "../types";
import { get, put, post } from "./client";

export const monitorApi = {
  getMonitorTrends: (days = 7) => get<MonitorTrends>(`/monitor/trends?days=${days}`),

  getMonitorModelUsage: (days = 7) => get<import("../types").ModelUsageReport>(`/monitor/model-usage?days=${days}`),

  getMonitorStats: () => get<MonitorStats>("/monitor/stats"),

  getMonitorReport: () => get<MonitorReport>("/monitor/report"),

  getMonitorHealth: () => get<{ healthy: boolean; status: string; components: Record<string, unknown> }>("/monitor/health"),

  getAlertConfig: () => get<AlertConfig>("/monitor/alerts"),

  saveAlertConfig: (body: AlertConfig) => put<AlertConfig>("/monitor/alerts", body),

  testAlertConfig: (body: AlertConfig) => post<{ ok: boolean; message?: string; status?: number }>("/monitor/alerts/test", body),
};
