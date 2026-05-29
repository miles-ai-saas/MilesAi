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
          <h2 className="text-base font-semibold text-ink">Webhook 告警</h2>
          <p className="mt-1 text-sm text-ink-muted">任务失败或组件健康降级时，向指定 URL 发送 JSON 通知。</p>
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
          </div>
          <div className="mt-6 flex flex-wrap gap-3">
            <button type="button" onClick={() => void onSaveAlerts()} className="btn-primary">
              保存配置
            </button>
            <button type="button" onClick={() => void onTestAlert()} className="btn-ghost" disabled={!alerts.webhook_url}>
              发送测试
            </button>
          </div>
        </section>
      </div>
    </>
  );
}
