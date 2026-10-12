"use client";

import type { EvalPageVm } from "@/features/eval/hooks/use-eval-page";
import {
  evalRunStatusLabel,
  evalScoringModeLabel,
  formatRunSummary,
  isEvalRunActive,
} from "@/features/eval/lib/eval-labels";

export function EvalRunDetailTab({ vm }: { vm: EvalPageVm }) {
  const {
    selectedRunId,
    runDetail,
    runItems,
    runItemsTotal,
    runItemsPage,
    setRunItemsPage,
    runDetailLoading,
    runDetailError,
    startRun,
  } = vm;

  if (!selectedRunId) {
    return (
      <div className="rounded-lg border border-dashed border-line px-6 py-16 text-center">
        <p className="text-sm text-ink-muted">请从「运行」Tab 选择一条记录，或通过 URL 参数 ?run= 打开详情。</p>
      </div>
    );
  }

  if (runDetailLoading && !runDetail) {
    return <p className="py-12 text-center text-sm text-ink-muted animate-pulse">加载中…</p>;
  }

  if (runDetailError && !runDetail) {
    return <p className="py-12 text-center text-sm text-red-600">{runDetailError}</p>;
  }

  if (!runDetail) return null;

  const pageSize = 20;
  const totalPages = Math.max(1, Math.ceil(runItemsTotal / pageSize));

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-line p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-2">
            <h2 className="text-lg font-semibold text-ink">运行详情</h2>
            <p className="font-mono text-xs text-ink-faint">{runDetail.id}</p>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-muted">
              <span>状态：{evalRunStatusLabel(runDetail.status)}</span>
              <span>模式：{evalScoringModeLabel(runDetail.scoring_mode)}</span>
              <span>{formatRunSummary(runDetail.summary)}</span>
            </div>
            {isEvalRunActive(runDetail.status) ? (
              <p className="text-xs text-brand">运行中，自动刷新中…</p>
            ) : null}
            {runDetail.error_message ? (
              <p className="text-sm text-red-600">{runDetail.error_message}</p>
            ) : null}
          </div>
          {runDetail.status === "pending" ? (
            <button type="button" className="btn-sm-primary" onClick={() => void startRun(runDetail)}>
              启动
            </button>
          ) : null}
        </div>
        <dl className="mt-4 grid gap-2 text-xs text-ink-faint sm:grid-cols-2">
          <div>
            <dt className="inline text-ink-muted">Dataset：</dt>
            <dd className="inline font-mono">{runDetail.dataset_id}</dd>
          </div>
          <div>
            <dt className="inline text-ink-muted">Agent：</dt>
            <dd className="inline font-mono">{runDetail.agent_id}</dd>
          </div>
          <div>
            <dt className="inline text-ink-muted">创建：</dt>
            <dd className="inline">{new Date(runDetail.created_at).toLocaleString()}</dd>
          </div>
          {runDetail.finished_at ? (
            <div>
              <dt className="inline text-ink-muted">结束：</dt>
              <dd className="inline">{new Date(runDetail.finished_at).toLocaleString()}</dd>
            </div>
          ) : null}
        </dl>
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-medium text-ink">用例结果（{runItemsTotal}）</h3>
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-line bg-surface-muted/40 text-xs text-ink-muted">
              <tr>
                <th className="px-3 py-2 font-medium">状态</th>
                <th className="px-3 py-2 font-medium">通过</th>
                <th className="px-3 py-2 font-medium">得分</th>
                <th className="px-3 py-2 font-medium">耗时</th>
                <th className="px-3 py-2 font-medium">答案预览</th>
                <th className="px-3 py-2 font-medium">call_id</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {runItems.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-ink-muted">
                    {runDetail.status === "pending" ? "尚未启动，暂无结果。" : "暂无结果项。"}
                  </td>
                </tr>
              ) : (
                runItems.map((item) => (
                  <tr key={item.id} className="align-top">
                    <td className="px-3 py-2 text-ink-muted">{item.status}</td>
                    <td className="px-3 py-2">
                      {item.passed === true ? (
                        <span className="text-green-700">通过</span>
                      ) : item.passed === false ? (
                        <span className="text-red-600">未通过</span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-3 py-2">{item.score ?? "—"}</td>
                    <td className="px-3 py-2">{item.latency_ms} ms</td>
                    <td className="max-w-xs px-3 py-2 text-xs text-ink-muted line-clamp-2">
                      {item.answer_preview || item.error_message || "—"}
                    </td>
                    <td className="px-3 py-2 font-mono text-[11px] text-ink-faint">
                      {item.call_id || "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {totalPages > 1 ? (
          <div className="flex items-center justify-end gap-2 text-sm">
            <button
              type="button"
              className="btn-ghost text-xs"
              disabled={runItemsPage <= 1}
              onClick={() => setRunItemsPage((p) => Math.max(1, p - 1))}
            >
              上一页
            </button>
            <span className="text-ink-muted">
              {runItemsPage} / {totalPages}
            </span>
            <button
              type="button"
              className="btn-ghost text-xs"
              disabled={runItemsPage >= totalPages}
              onClick={() => setRunItemsPage((p) => p + 1)}
            >
              下一页
            </button>
          </div>
        ) : null}
      </section>
    </div>
  );
}
