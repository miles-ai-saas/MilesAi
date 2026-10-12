"use client";

import { PageMessage } from "@/components/ui/PageMessage";
import type { MonitorPageVm } from "@/features/monitor/hooks/use-monitor-page";

export function MonitorAlertsTab({ vm }: { vm: MonitorPageVm }) {
  const { alerts, setAlerts, alertMsg, setAlertMsg, onSaveAlerts, onTestAlert } = vm;

  return (
    <>
      {alertMsg && <PageMessage message={alertMsg} onDismiss={() => setAlertMsg("")} />}
      <div className="col-span-full mx-auto w-full max-w-2xl">
        <section className="rounded-xl border border-line bg-surface p-6 shadow-panel">
          <h2 className="text-base font-semibold text-ink">告警通知</h2>
          <p className="mt-1 text-sm text-ink-muted">任务失败、健康降级或本月 Token 达阈值时，向 Webhook / 邮件发送通知。</p>
          <label className="mt-5 flex cursor-pointer items-center gap-2 text-sm text-ink">
            <input type="checkbox" checked={alerts.enabled} onChange={(e) => setAlerts({ ...alerts, enabled: e.target.checked })} />
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
          <label className="mt-4 block space-y-1">
            <span className="text-xs text-ink-muted">邮件收件人（逗号分隔，可选）</span>
            <input
              className="input-field w-full"
              placeholder="ops@example.com"
              value={alerts.email_notify_to ?? ""}
              onChange={(e) => setAlerts({ ...alerts, email_notify_to: e.target.value })}
            />
          </label>
          <div className="mt-4 space-y-2 rounded-lg border border-line-soft bg-surface-muted p-4">
            <p className="text-xs font-medium text-ink-muted">通知条件</p>
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={alerts.notify_on_task_failed}
                onChange={(e) => setAlerts({ ...alerts, notify_on_task_failed: e.target.checked })}
              />
              异步任务失败时通知
            </label>
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={alerts.notify_on_health_degraded}
                onChange={(e) => setAlerts({ ...alerts, notify_on_health_degraded: e.target.checked })}
              />
              组件健康降级时通知
            </label>
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={alerts.notify_on_tokens_monthly_threshold}
                onChange={(e) => setAlerts({ ...alerts, notify_on_tokens_monthly_threshold: e.target.checked })}
              />
              本月 Token 达阈值时通知
            </label>
            <label className="mt-2 flex items-center gap-2 text-sm">
              <span className="text-ink-muted">阈值</span>
              <input
                type="number"
                min={1}
                max={100}
                className="input-field w-20"
                value={alerts.tokens_monthly_warn_percent}
                onChange={(e) =>
                  setAlerts({
                    ...alerts,
                    tokens_monthly_warn_percent: Math.min(100, Math.max(1, Number(e.target.value) || 80)),
                  })
                }
              />
              <span className="text-ink-muted">%</span>
            </label>
          </div>
          <div className="mt-6 flex flex-wrap gap-3">
            <button type="button" onClick={() => void onSaveAlerts()} className="btn-primary">
              保存配置
            </button>
            <button
              type="button"
              onClick={() => void onTestAlert()}
              className="btn-ghost"
              disabled={!alerts.webhook_url && !alerts.email_notify_to}
            >
              发送测试
            </button>
          </div>
        </section>
      </div>
    </>
  );
}
