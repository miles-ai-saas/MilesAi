"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { useKbMeta } from "@/features/kb";
import { useMonitorMeta } from "@/features/monitor/hooks/use-monitor-meta";
import type { MonitorTab, MonitorHealthPayload } from "@/features/monitor/lib/monitor-shared";
import type { AlertConfig, ModelUsageReport, MonitorReport, MonitorTrends } from "@/lib/types";

export function useMonitorPage() {
  const { ready } = useRequireAuth();
  const monitorMeta = useMonitorMeta(ready);
  const kbMeta = useKbMeta(ready);
  const [trendDays, setTrendDays] = useState(7);
  const [tab, setTab] = useState<MonitorTab>("overview");
  const [loading, setLoading] = useState(true);
  const [report, setReport] = useState<MonitorReport | null>(null);
  const [trends, setTrends] = useState<MonitorTrends | null>(null);
  const [modelUsage, setModelUsage] = useState<ModelUsageReport | null>(null);
  const [health, setHealth] = useState<MonitorHealthPayload | null>(null);
  const [alerts, setAlerts] = useState<AlertConfig>({
    enabled: false,
    webhook_url: "",
    notify_on_task_failed: true,
    notify_on_health_degraded: true,
  });
  const [alertMsg, setAlertMsg] = useState("");
  const [redisInfo, setRedisInfo] = useState<Record<string, unknown> | null>(null);
  const [workerInfo, setWorkerInfo] = useState<Record<string, unknown> | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [r, t, u, h, a] = await Promise.all([
        api.getMonitorReport(),
        api.getMonitorTrends(trendDays),
        api.getMonitorModelUsage(trendDays),
        api.getMonitorHealth(),
        api.getAlertConfig(),
      ]);
      setReport(r);
      setTrends(t);
      setModelUsage(u);
      setHealth(h);
      setAlerts(a);
      void api
        .getRedisInfo()
        .then(setRedisInfo)
        .catch(() => {});
      void api
        .getWorkerInfo()
        .then(setWorkerInfo)
        .catch(() => {});
    } finally {
      setLoading(false);
    }
  }, [trendDays]);

  useEffect(() => {
    if (!ready) return;
    void reload();
  }, [ready, reload]);

  const onExport = async () => {
    const blob = await api.exportMonitorReport();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "milesai-report.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const onSaveAlerts = async () => {
    await api.saveAlertConfig(alerts);
    setAlertMsg("告警配置已保存");
  };

  const onTestAlert = async () => {
    const res = await api.testAlertConfig(alerts);
    setAlertMsg(res.ok ? "测试通知已发送" : res.message || "发送失败");
  };

  const statCards = useMemo(() => {
    if (!report) return [];
    return [
      { label: "知识库", value: String(report.stats.knowledge_bases), hint: "租户内知识库总数" },
      { label: "文档", value: String(report.stats.documents), hint: "已上传文档数量" },
      { label: "智能体", value: String(report.stats.agents), hint: "已创建智能体" },
      { label: "流程", value: String(report.stats.flows), hint: "流程编排数量" },
      { label: "今日拦截", value: String(report.stats.intercept_logs_today), hint: "合规拦截次数" },
      { label: "待处理文档", value: String(report.stats.pending_documents), hint: "排队或处理中" },
      { label: "应用安装", value: String(report.marketplace_installs), hint: "应用市场安装数" },
      {
        label: "异步任务",
        value: String(report.tasks.total),
        hint: `成功 ${report.tasks.success} · 失败 ${report.tasks.failed} · 运行 ${report.tasks.running}`,
      },
    ];
  }, [report]);

  const onTabChange = (k: string) => {
    setTab(k as MonitorTab);
    setAlertMsg("");
  };

  return {
    monitorMeta,
    kbMeta,
    trendDays,
    setTrendDays,
    tab,
    setTab,
    loading,
    report,
    trends,
    modelUsage,
    health,
    alerts,
    setAlerts,
    alertMsg,
    setAlertMsg,
    redisInfo,
    workerInfo,
    reload,
    onExport,
    onSaveAlerts,
    onTestAlert,
    statCards,
    onTabChange,
  };
}

export type MonitorPageVm = ReturnType<typeof useMonitorPage>;
