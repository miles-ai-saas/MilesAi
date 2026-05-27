"use client";

/** 监控大盘（链路 §14）：统计/趋势/健康 + `useMonitorMeta`。 */

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { SimpleBarChart } from "@/components/charts/SimpleBarChart";
import { documentStatusLabel } from "@/lib/document-status";
import {
  monitorHealthComponentLabel,
  monitorOverallHealthLabel,
  monitorTrendDayOptions,
} from "@/lib/monitor-labels";
import { useKbMeta } from "@/hooks/use-kb-meta";
import { useMonitorMeta } from "@/hooks/use-monitor-meta";
import type { AlertConfig, ModelUsageReport, MonitorReport, MonitorTrends } from "@/lib/types";

type Tab = "overview" | "trends" | "usage" | "health" | "alerts";

const MAIN_TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "概览" },
  { key: "trends", label: "趋势分析" },
  { key: "usage", label: "模型用量" },
  { key: "health", label: "系统健康" },
  { key: "alerts", label: "告警配置" },
];

const PAGE_DESC =
  "查看租户业务指标、异步任务与合规拦截趋势，检查依赖组件健康状态，并配置 Webhook 告警。";

/** 与后端 collect_health_status 主键一致；weaviate/minio 为兼容别名不在此展示 */
const PRIMARY_COMPONENT_KEYS = ["postgres", "redis", "vector_store", "object_storage"] as const;

type MonitorHealthPayload = {
  healthy?: boolean;
  status?: string;
  components?: Record<string, unknown>;
};

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
  return PRIMARY_COMPONENT_KEYS.filter((k) => k in components).map(
    (k) => [k, components[k]] as const,
  );
}

function StatChip({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface px-4 py-3 shadow-card">
      <p className="text-xs text-ink-muted">{label}</p>
      <p className="mt-0.5 text-2xl font-bold tabular-nums text-brand">{value}</p>
      {hint ? <p className="mt-1 text-xs text-ink-faint line-clamp-2">{hint}</p> : null}
    </div>
  );
}

function PageMessage({ message, onDismiss }: { message: string; onDismiss?: () => void }) {
  return (
    <div className="col-span-full flex items-start justify-between gap-3 rounded-xl border border-line bg-brand-light/40 px-4 py-3 text-sm text-ink">
      <p className="min-w-0 flex-1">{message}</p>
      {onDismiss && (
        <button type="button" className="shrink-0 text-xs text-ink-muted hover:text-ink" onClick={onDismiss}>
          关闭
        </button>
      )}
    </div>
  );
}

function ChartPanel({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-line bg-surface p-5 shadow-card">
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      {subtitle && <p className="mt-1 text-xs text-ink-muted">{subtitle}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function HealthStatusBadge({
  ok,
  status,
  monitorMeta,
}: {
  ok: boolean;
  status?: string;
  monitorMeta: import("@/lib/types").MonitorMeta | null;
}) {
  const label = monitorOverallHealthLabel(status, ok, monitorMeta);
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${
        ok
          ? "bg-emerald-50 text-emerald-800 ring-emerald-200"
          : "bg-amber-50 text-amber-800 ring-amber-200"
      }`}
    >
      {label}
    </span>
  );
}

function HealthComponents({
  components,
  monitorMeta,
}: {
  components: Record<string, unknown>;
  monitorMeta: import("@/lib/types").MonitorMeta | null;
}) {
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

export default function MonitorPage() {
  const { ready } = useRequireAuth();
  const monitorMeta = useMonitorMeta(ready);
  const kbMeta = useKbMeta(ready);
  const [trendDays, setTrendDays] = useState(7);
  const [tab, setTab] = useState<Tab>("overview");
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
      {
        label: "今日拦截",
        value: String(report.stats.intercept_logs_today),
        hint: "合规拦截次数",
      },
      {
        label: "待处理文档",
        value: String(report.stats.pending_documents),
        hint: "排队或处理中",
      },
      { label: "应用安装", value: String(report.marketplace_installs), hint: "应用市场安装数" },
      {
        label: "异步任务",
        value: String(report.tasks.total),
        hint: `成功 ${report.tasks.success} · 失败 ${report.tasks.failed} · 运行 ${report.tasks.running}`,
      },
    ];
  }, [report]);

  const layoutCommon = {
    title: "监控",
    description: PAGE_DESC,
    tabs: MAIN_TABS,
    activeTab: tab,
    onTabChange: (k: string) => {
      setTab(k as Tab);
      setAlertMsg("");
    },
    search: "",
    onSearchChange: () => {},
    showSearch: false,
    loading,
    headerAction: (
      <div className="flex shrink-0 gap-2">
        <button type="button" onClick={() => void reload()} className="btn-ghost text-sm" disabled={loading}>
          {loading ? "刷新中…" : "刷新"}
        </button>
        <button type="button" onClick={onExport} className="btn-ghost text-sm" disabled={!report}>
          导出 CSV
        </button>
      </div>
    ),
  };

  if (tab === "trends") {
    const trendHint =
      monitorTrendDayOptions(monitorMeta).find((o) => o.value === String(trendDays))?.label ??
      `近 ${trendDays} 天`;
    return (
      <ResourceListLayout
        {...layoutCommon}
        loading={loading}
        headerAction={
          <select
            className="input-field w-auto shrink-0 text-sm"
            value={String(trendDays)}
            onChange={(e) => setTrendDays(Number(e.target.value) || 7)}
            aria-label="趋势天数"
          >
            {monitorTrendDayOptions(monitorMeta).map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        }
      >
        {!report || !trends ? (
          <p className="col-span-full py-12 text-center text-sm text-ink-muted">加载趋势数据…</p>
        ) : (
        <div className="col-span-full space-y-5">
          <ChartPanel title="任务趋势" subtitle={`${trendHint}每日任务总量`}>
            {trends.task_by_day.length === 0 ? (
              <p className="text-xs text-ink-faint">暂无任务数据</p>
            ) : (
              <SimpleBarChart
                items={trends.task_by_day.map((d) => ({
                  label: d.date.slice(5),
                  value: d.total,
                }))}
              />
            )}
          </ChartPanel>

          <div className="grid gap-5 lg:grid-cols-2">
            <ChartPanel title="任务状态分布" subtitle="当前租户累计">
              <SimpleBarChart
                items={[
                  { label: "成功", value: report.tasks.success, color: "#059669" },
                  { label: "失败", value: report.tasks.failed, color: "#dc2626" },
                  { label: "运行", value: report.tasks.running, color: "#d97706" },
                  { label: "等待", value: report.tasks.pending, color: "#6b7280" },
                ]}
              />
            </ChartPanel>
            <ChartPanel title="合规拦截趋势" subtitle={`${trendHint}按日统计`}>
              {trends.intercept_by_day.length === 0 ? (
                <p className="text-xs text-ink-faint">暂无拦截数据</p>
              ) : (
                <SimpleBarChart
                  items={trends.intercept_by_day.map((d) => ({
                    label: String(d.date).slice(5),
                    value: d.count,
                    color: "#dc2626",
                  }))}
                />
              )}
            </ChartPanel>
          </div>

          <ChartPanel title="文档状态分布" subtitle="按处理状态汇总">
            {Object.keys(report.documents_by_status).length === 0 ? (
              <p className="text-xs text-ink-faint">暂无文档</p>
            ) : (
              <SimpleBarChart
                items={Object.entries(report.documents_by_status).map(([k, v]) => ({
                  label: documentStatusLabel(k, kbMeta?.document_statuses),
                  value: v,
                }))}
              />
            )}
          </ChartPanel>
        </div>
        )}
      </ResourceListLayout>
    );
  }

  if (tab === "usage") {
    return (
      <ResourceListLayout {...layoutCommon} loading={loading}>
        <div className="col-span-full space-y-4">
          <StatChip
            label={`近 ${trendDays} 天总 Token`}
            value={String(modelUsage?.total_tokens ?? 0)}
            hint="来自对话类模型调用（LiteLLM usage）"
          />
          {!modelUsage?.rows.length ? (
            <p className="rounded-xl border border-dashed border-line py-12 text-center text-sm text-ink-faint">
              暂无用量数据，智能体对话后将在此汇总
            </p>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-line bg-surface shadow-card">
              <table className="w-full min-w-[520px] text-left text-sm">
                <thead className="border-b border-line-soft bg-surface-muted text-xs text-ink-muted">
                  <tr>
                    <th className="px-4 py-2 font-medium">模型</th>
                    <th className="px-4 py-2 font-medium">调用次数</th>
                    <th className="px-4 py-2 font-medium">输入 Token</th>
                    <th className="px-4 py-2 font-medium">输出 Token</th>
                    <th className="px-4 py-2 font-medium">合计</th>
                  </tr>
                </thead>
                <tbody>
                  {modelUsage.rows.map((row) => (
                    <tr key={row.model_config_id ?? row.model_name} className="border-b border-line-soft">
                      <td className="px-4 py-2 font-medium text-ink">{row.model_name}</td>
                      <td className="px-4 py-2 tabular-nums">{row.call_count}</td>
                      <td className="px-4 py-2 tabular-nums">{row.prompt_tokens}</td>
                      <td className="px-4 py-2 tabular-nums">{row.completion_tokens}</td>
                      <td className="px-4 py-2 tabular-nums text-brand">{row.total_tokens}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </ResourceListLayout>
    );
  }

  if (tab === "health") {
    const components = health?.components ?? {};
    return (
      <ResourceListLayout {...layoutCommon} loading={loading}>
        <div className="col-span-full mx-auto w-full max-w-3xl space-y-4">
          <section className="rounded-xl border border-line bg-surface p-5 shadow-panel">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-ink">整体状态</h2>
                <p className="mt-1 text-sm text-ink-muted">数据库、向量库、消息队列等依赖探测结果</p>
              </div>
              <HealthStatusBadge
                ok={health?.healthy ?? health?.status === "healthy"}
                status={health?.status}
                monitorMeta={monitorMeta}
              />
            </div>
          </section>
          <section className="rounded-xl border border-line bg-surface p-5 shadow-panel">
            <h3 className="text-sm font-semibold text-ink">组件明细</h3>
            <div className="mt-4">
              {health ? (
                <HealthComponents components={components} monitorMeta={monitorMeta} />
              ) : (
                <p className="text-sm text-ink-muted">加载中…</p>
              )}
            </div>
          </section>
        </div>
      </ResourceListLayout>
    );
  }

  if (tab === "alerts") {
    return (
      <ResourceListLayout {...layoutCommon} loading={loading}>
        {alertMsg && <PageMessage message={alertMsg} onDismiss={() => setAlertMsg("")} />}
        <div className="col-span-full mx-auto w-full max-w-2xl">
          <section className="rounded-xl border border-line bg-surface p-6 shadow-panel">
            <h2 className="text-base font-semibold text-ink">Webhook 告警</h2>
            <p className="mt-1 text-sm text-ink-muted">
              任务失败或组件健康降级时，向指定 URL 发送 JSON 通知。
            </p>
            <label className="mt-5 flex cursor-pointer items-center gap-2 text-sm text-ink">
              <input
                type="checkbox"
                checked={alerts.enabled}
                onChange={(e) => setAlerts({ ...alerts, enabled: e.target.checked })}
              />
              启用告警
            </label>
            <label className="mt-4 block space-y-1">
              <span className="text-xs text-ink-muted">Webhook URL</span>
              <input
                className="input-field w-full"
                placeholder="https://your-webhook.example/hooks/xxx"
                value={alerts.webhook_url}
                onChange={(e) => setAlerts({ ...alerts, webhook_url: e.target.value })}
              />
            </label>
            <div className="mt-4 space-y-2 rounded-lg border border-line-soft bg-surface-muted p-4">
              <p className="text-xs font-medium text-ink-muted">通知条件</p>
              <label className="flex cursor-pointer items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={alerts.notify_on_task_failed}
                  onChange={(e) =>
                    setAlerts({ ...alerts, notify_on_task_failed: e.target.checked })
                  }
                />
                异步任务失败时通知
              </label>
              <label className="flex cursor-pointer items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={alerts.notify_on_health_degraded}
                  onChange={(e) =>
                    setAlerts({ ...alerts, notify_on_health_degraded: e.target.checked })
                  }
                />
                组件健康降级时通知
              </label>
            </div>
            <div className="mt-6 flex flex-wrap gap-3">
              <button type="button" onClick={onSaveAlerts} className="btn-primary">
                保存配置
              </button>
              <button type="button" onClick={onTestAlert} className="btn-ghost" disabled={!alerts.webhook_url}>
                发送测试
              </button>
            </div>
          </section>
        </div>
      </ResourceListLayout>
    );
  }

  return (
    <ResourceListLayout {...layoutCommon} loading={loading}>
      {report && (
        <>
          <div className="col-span-full grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {statCards.map((c) => (
              <StatChip key={c.label} label={c.label} value={c.value} hint={c.hint} />
            ))}
          </div>
          <div className="col-span-full grid gap-4 lg:grid-cols-2">
            <section className="rounded-xl border border-line bg-surface p-5 shadow-card">
              <h3 className="text-sm font-semibold text-ink">任务概况</h3>
              {trends && trends.task_by_day.length > 0 ? (
                <SimpleBarChart
                  className="mt-4"
                  items={trends.task_by_day.slice(-5).map((d) => ({
                    label: d.date.slice(5),
                    value: d.total,
                  }))}
                />
              ) : (
                <p className="mt-3 text-xs text-ink-faint">暂无近期任务数据</p>
              )}
              <button
                type="button"
                className="mt-4 text-xs text-brand hover:underline"
                onClick={() => setTab("trends")}
              >
                查看完整趋势 →
              </button>
            </section>
            <section className="rounded-xl border border-line bg-surface p-5 shadow-card">
              <h3 className="text-sm font-semibold text-ink">合规与文档</h3>
              <dl className="mt-4 space-y-3 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-ink-muted">今日拦截</dt>
                  <dd className="font-semibold tabular-nums text-ink">
                    {report.stats.intercept_logs_today}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-ink-muted">待处理文档</dt>
                  <dd className="font-semibold tabular-nums text-ink">
                    {report.stats.pending_documents}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-ink-muted">文档总数</dt>
                  <dd className="font-semibold tabular-nums text-ink">{report.stats.documents}</dd>
                </div>
              </dl>
              <button
                type="button"
                className="mt-4 text-xs text-brand hover:underline"
                onClick={() => setTab("trends")}
              >
                查看趋势图表 →
              </button>
            </section>
          </div>
          <div className="col-span-full flex flex-wrap gap-3 rounded-xl border border-dashed border-line px-4 py-3">
            <button type="button" className="text-sm text-brand hover:underline" onClick={() => setTab("health")}>
              检查系统健康
            </button>
            <span className="text-ink-faint">·</span>
            <button type="button" className="text-sm text-brand hover:underline" onClick={() => setTab("alerts")}>
              配置告警 Webhook
            </button>
          </div>
        </>
      )}
    </ResourceListLayout>
  );
}
