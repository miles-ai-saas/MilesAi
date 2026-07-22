"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { useKbMeta } from "@/features/kb";
import { useMonitorMeta } from "@/features/monitor/hooks/use-monitor-meta";
import type { AlertConfig, ModelUsageReport, MonitorReport, MonitorTrends } from "@/lib/types";

export type MonitorTab = "overview" | "trends" | "usage" | "health" | "alerts";

export type MonitorHealthPayload = {
  healthy?: boolean;
  status?: string;
  components?: Record<string, unknown>;
};

/** 被缓存的 Tab 数据加载状态 */
type TabLoadingMap = Partial<Record<MonitorTab, boolean>>;

export function useMonitorPage() {
  const { ready } = useRequireAuth();
  const monitorMeta = useMonitorMeta(ready);
  const kbMeta = useKbMeta(ready);
  const [trendDays, setTrendDays] = useState(7);
  const [tab, setTab] = useState<MonitorTab>("overview");

  // ── 各 Tab 数据 ──
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

  // ── 各 Tab 独立 loading 状态 ──
  const [tabLoading, setTabLoading] = useState<TabLoadingMap>({});

  /** 标记哪些 Tab 的数据已加载完成（避免重复请求） */
  const loaded = useRef(new Set<MonitorTab>());

  // ── Tab 级加载函数（幂等：已加载则跳过） ──

  const loadOverview = useCallback(async () => {
    if (loaded.current.has("overview")) return;
    setTabLoading((p) => ({ ...p, overview: true }));
    try {
      const [r, t] = await Promise.all([api.getMonitorReport(), api.getMonitorTrends(trendDays)]);
      setReport(r);
      setTrends(t);
      loaded.current.add("overview");
    } finally {
      setTabLoading((p) => ({ ...p, overview: false }));
    }
  }, [trendDays]);

  const loadTrends = useCallback(async () => {
    if (loaded.current.has("trends")) return;
    setTabLoading((p) => ({ ...p, trends: true }));
    try {
      // trends 数据在 loadOverview 时已拉取，这里保证 report 也已加载
      const [r, t] = await Promise.all([api.getMonitorReport(), api.getMonitorTrends(trendDays)]);
      if (!loaded.current.has("overview")) {
        setReport(r);
        loaded.current.add("overview");
      }
      setTrends(t);
      loaded.current.add("trends");
    } finally {
      setTabLoading((p) => ({ ...p, trends: false }));
    }
  }, [trendDays]);

  const loadUsage = useCallback(async () => {
    if (loaded.current.has("usage")) return;
    setTabLoading((p) => ({ ...p, usage: true }));
    try {
      const u = await api.getMonitorModelUsage(trendDays);
      setModelUsage(u);
      loaded.current.add("usage");
    } finally {
      setTabLoading((p) => ({ ...p, usage: false }));
    }
  }, [trendDays]);

  const loadHealth = useCallback(async () => {
    if (loaded.current.has("health")) return;
    setTabLoading((p) => ({ ...p, health: true }));
    try {
      const h = await api.getMonitorHealth();
      setHealth(h);
      void api
        .getRedisInfo()
        .then(setRedisInfo)
        .catch(() => {});
      void api
        .getWorkerInfo()
        .then(setWorkerInfo)
        .catch(() => {});
      loaded.current.add("health");
    } finally {
      setTabLoading((p) => ({ ...p, health: false }));
    }
  }, []);

  const loadAlerts = useCallback(async () => {
    if (loaded.current.has("alerts")) return;
    setTabLoading((p) => ({ ...p, alerts: true }));
    try {
      const a = await api.getAlertConfig();
      setAlerts(a);
      loaded.current.add("alerts");
    } finally {
      setTabLoading((p) => ({ ...p, alerts: false }));
    }
  }, []);

  // ── 页面挂载／Tab 切换／趋势天数变化时按需加载 ──

  // 页面首次就绪：只加载概览 Tab 数据
  useEffect(() => {
    if (!ready) return;
    void loadOverview();
  }, [ready, loadOverview]);

  // Tab 切换时：按需加载目标 Tab 数据
  useEffect(() => {
    if (!ready) return;
    switch (tab) {
      case "overview":
        void loadOverview();
        break;
      case "trends":
        void loadTrends();
        break;
      case "usage":
        void loadUsage();
        break;
      case "health":
        void loadHealth();
        break;
      case "alerts":
        void loadAlerts();
        break;
    }
  }, [ready, tab, loadOverview, loadTrends, loadUsage, loadHealth, loadAlerts]);

  // 趋势天数变化：只刷新 trends 和 modelUsage（如果对应 Tab 已加载过）
  useEffect(() => {
    if (!ready) return;
    // 标记对应 Tab 为未加载，下次切换时会自动刷新
    loaded.current.delete("overview");
    loaded.current.delete("trends");
    loaded.current.delete("usage");
    // 如果当前正在看这些 Tab，立即刷新
    if (tab === "overview") void loadOverview();
    else if (tab === "trends") void loadTrends();
    else if (tab === "usage") void loadUsage();
  }, [trendDays]); // eslint-disable-line react-hooks/exhaustive-deps

  // 手动刷新：重置所有标记，重新加载当前 Tab
  const reload = useCallback(() => {
    loaded.current.clear();
    // 触发当前 Tab 重新加载
    setTabLoading((p) => ({ ...p, [tab]: true }));
    (async () => {
      try {
        switch (tab) {
          case "overview": {
            const [r, t] = await Promise.all([api.getMonitorReport(), api.getMonitorTrends(trendDays)]);
            setReport(r);
            setTrends(t);
            loaded.current.add("overview");
            break;
          }
          case "trends": {
            const [r, t] = await Promise.all([api.getMonitorReport(), api.getMonitorTrends(trendDays)]);
            setReport(r);
            setTrends(t);
            loaded.current.add("trends");
            break;
          }
          case "usage": {
            const u = await api.getMonitorModelUsage(trendDays);
            setModelUsage(u);
            loaded.current.add("usage");
            break;
          }
          case "health": {
            const h = await api.getMonitorHealth();
            setHealth(h);
            void api.getRedisInfo().then(setRedisInfo).catch(() => {});
            void api.getWorkerInfo().then(setWorkerInfo).catch(() => {});
            loaded.current.add("health");
            break;
          }
          case "alerts": {
            const a = await api.getAlertConfig();
            setAlerts(a);
            loaded.current.add("alerts");
            break;
          }
        }
      } finally {
        setTabLoading((p) => ({ ...p, [tab]: false }));
      }
    })();
  }, [tab, trendDays]);

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

  /** 统合 loading：页面初始 loading 或当前 Tab 正在加载 */
  const loading = ready ? (tabLoading[tab] ?? false) : true;

  return {
    monitorMeta,
    kbMeta,
    trendDays,
    setTrendDays,
    tab,
    setTab,
    tabLoading,
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
    onSaveAlerts,
    onTestAlert,
    statCards,
    onTabChange,
  };
}

export type MonitorPageVm = ReturnType<typeof useMonitorPage>;
