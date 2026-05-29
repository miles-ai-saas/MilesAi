/** 监控页 Tab 与健康 payload 类型。 */

export type MonitorTab = "overview" | "trends" | "usage" | "health" | "alerts";

export type MonitorHealthPayload = {
  healthy?: boolean;
  status?: string;
  components?: Record<string, unknown>;
};
