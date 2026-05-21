"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { SimpleBarChart } from "@/components/charts/SimpleBarChart";
import { documentStatusLabel } from "@/lib/document-status";
import type { AlertConfig, MonitorReport, MonitorTrends } from "@/lib/types";

export default function MonitorPage() {
  const { ready } = useRequireAuth();
  const [report, setReport] = useState<MonitorReport | null>(null);
  const [trends, setTrends] = useState<MonitorTrends | null>(null);
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [alerts, setAlerts] = useState<AlertConfig>({
    enabled: false,
    webhook_url: "",
    notify_on_task_failed: true,
    notify_on_health_degraded: true,
  });
  const [alertMsg, setAlertMsg] = useState("");

  const reload = async () => {
    const [r, t, h, a] = await Promise.all([
      api.getMonitorReport(),
      api.getMonitorTrends(7),
      api.getMonitorHealth(),
      api.getAlertConfig(),
    ]);
    setReport(r);
    setTrends(t);
    setHealth(h);
    setAlerts(a);
  };

  useEffect(() => {
    if (!ready) return;
    reload();
  }, [ready]);

  const onExport = async () => {
    const blob = await api.exportMonitorReport();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "aiengine-report.csv";
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

  const statCards = report
    ? [
        { title: "知识库", value: String(report.stats.knowledge_bases), desc: "租户内知识库总数" },
        { title: "文档", value: String(report.stats.documents), desc: "已上传文档数量" },
        { title: "智能体", value: String(report.stats.agents), desc: "已创建智能体" },
        { title: "流程", value: String(report.stats.flows), desc: "流程编排数量" },
        { title: "今日拦截", value: String(report.stats.intercept_logs_today), desc: "合规拦截次数" },
        { title: "待处理文档", value: String(report.stats.pending_documents), desc: "排队或处理中" },
        { title: "应用安装", value: String(report.marketplace_installs), desc: "应用市场安装数" },
        {
          title: "异步任务",
          value: String(report.tasks.total),
          desc: `成功 ${report.tasks.success} · 失败 ${report.tasks.failed} · 运行 ${report.tasks.running}`,
        },
      ]
    : [];

  return (
    <div className="space-y-8">
      <ResourceListLayout
        title="监控"
        description="查看业务指标、任务汇总与组件健康状态，配置告警 Webhook。"
        search=""
        onSearchChange={() => {}}
        showSearch={false}
        loading={!report}
        headerAction={
          <button type="button" onClick={onExport} className="btn-ghost shrink-0">
            导出 CSV
          </button>
        }
      >
        {statCards.map((c) => (
          <ResourceItemCard
            key={c.title}
            title={c.title}
            description={c.desc}
            meta={<span className="text-2xl font-bold text-brand">{c.value}</span>}
          />
        ))}
      </ResourceListLayout>

      {report && trends && (
        <div className="resource-page-shell space-y-5">
          <section className="card p-4">
            <h2 className="text-sm font-semibold text-ink">任务趋势（近 7 天）</h2>
            {trends.task_by_day.length === 0 ? (
              <p className="mt-3 text-xs text-ink-faint">暂无任务数据</p>
            ) : (
              <SimpleBarChart
                className="mt-4"
                items={trends.task_by_day.map((d) => ({
                  label: d.date.slice(5),
                  value: d.total,
                }))}
              />
            )}
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <p className="mb-2 text-xs font-medium text-ink-muted">按状态（累计）</p>
                <SimpleBarChart
                  items={[
                    { label: "成功", value: report.tasks.success, color: "#059669" },
                    { label: "失败", value: report.tasks.failed, color: "#dc2626" },
                    { label: "运行", value: report.tasks.running, color: "#d97706" },
                    { label: "等待", value: report.tasks.pending, color: "#6b7280" },
                  ]}
                />
              </div>
              <div>
                <p className="mb-2 text-xs font-medium text-ink-muted">合规拦截（按日）</p>
                {trends.intercept_by_day.length === 0 ? (
                  <p className="text-xs text-ink-faint">暂无数据</p>
                ) : (
                  <SimpleBarChart
                    items={trends.intercept_by_day.map((d) => ({
                      label: String(d.date).slice(5),
                      value: d.count,
                    }))}
                  />
                )}
              </div>
            </div>
          </section>

          <section className="card p-4">
            <h2 className="text-sm font-semibold text-ink">文档状态分布</h2>
            {Object.keys(report.documents_by_status).length === 0 ? (
              <p className="mt-3 text-xs text-ink-faint">暂无文档</p>
            ) : (
              <SimpleBarChart
                className="mt-4"
                items={Object.entries(report.documents_by_status).map(([k, v]) => ({
                  label: documentStatusLabel(k),
                  value: v,
                }))}
              />
            )}
          </section>

          {health && (
            <section className="card p-4">
              <h2 className="text-sm font-semibold text-ink">组件健康</h2>
              <p className="mt-1 text-xs text-ink-muted">
                状态:{" "}
                <span
                  className={
                    (health as { healthy?: boolean }).healthy ? "text-emerald-600" : "text-amber-600"
                  }
                >
                  {(health as { status?: string }).status || "unknown"}
                </span>
              </p>
              <pre className="mt-2 max-h-48 overflow-auto rounded bg-surface-muted p-3 text-xs text-ink">
                {JSON.stringify((health as { components?: unknown }).components ?? health, null, 2)}
              </pre>
            </section>
          )}

          <section className="card p-4">
            <h2 className="text-sm font-semibold text-ink">告警 Webhook</h2>
            <label className="mt-3 flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={alerts.enabled}
                onChange={(e) => setAlerts({ ...alerts, enabled: e.target.checked })}
              />
              启用告警
            </label>
            <input
              className="input-field mt-2 w-full"
              placeholder="https://your-webhook.example/hooks/xxx"
              value={alerts.webhook_url}
              onChange={(e) => setAlerts({ ...alerts, webhook_url: e.target.value })}
            />
            <div className="mt-3 flex flex-wrap gap-3">
              <button type="button" onClick={onSaveAlerts} className="btn-primary">
                保存配置
              </button>
              <button type="button" onClick={onTestAlert} className="btn-ghost">
                发送测试
              </button>
            </div>
            {alertMsg && <p className="mt-2 text-xs text-ink-muted">{alertMsg}</p>}
          </section>
        </div>
      )}
    </div>
  );
}
