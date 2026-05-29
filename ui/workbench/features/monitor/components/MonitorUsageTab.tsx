"use client";

import { StatChip } from "@/components/ui/StatChip";
import type { MonitorPageVm } from "@/features/monitor/hooks/use-monitor-page";

export function MonitorUsageTab({ vm }: { vm: MonitorPageVm }) {
  const { modelUsage, trendDays } = vm;

  return (
    <div className="col-span-full space-y-4">
      <StatChip label={`近 ${trendDays} 天总 Token`} value={String(modelUsage?.total_tokens ?? 0)} hint="来自对话类模型调用（LiteLLM usage）" />
      {!modelUsage?.rows.length ? (
        <p className="rounded-xl border border-dashed border-line py-12 text-center text-sm text-ink-faint">暂无用量数据，智能体对话后将在此汇总</p>
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
  );
}
