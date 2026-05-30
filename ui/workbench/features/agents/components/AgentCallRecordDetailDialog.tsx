"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import {
  agentCallRouteLabel,
  agentCallStatusLabel,
  formatCallRecordTime,
  hookTriggerLabel,
} from "@/features/agents/lib/agent-call-record-labels";
import type { AgentCallRecordDetail } from "@/lib/types";
import Link from "next/link";

type Props = {
  agentId: string;
  callId: string | null;
  conversationId?: string;
  onClose: () => void;
  onOpenTrace?: () => void;
  onOpenTraceFromRecord?: (sessionId: string) => void | Promise<void>;
};

export function AgentCallRecordDetailDialog({
  agentId,
  callId,
  conversationId,
  onClose,
  onOpenTrace,
  onOpenTraceFromRecord,
}: Props) {
  const [detail, setDetail] = useState<AgentCallRecordDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copyHint, setCopyHint] = useState("");

  useEffect(() => {
    if (!callId) {
      setDetail(null);
      setError("");
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    void api
      .getAgentCallRecord(agentId, callId)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "加载失败");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [agentId, callId]);

  useEffect(() => {
    if (!copyHint) return;
    const t = window.setTimeout(() => setCopyHint(""), 2000);
    return () => window.clearTimeout(t);
  }, [copyHint]);

  if (!callId) return null;

  const canOpenTraceLocal = Boolean(
    onOpenTrace && detail?.conversation_id && conversationId && detail.conversation_id === conversationId,
  );
  const canOpenTraceFromServer = Boolean(onOpenTraceFromRecord && detail?.conversation_id);

  const onCopyTrace = async () => {
    if (!detail?.trace_id) return;
    try {
      await navigator.clipboard.writeText(detail.trace_id);
      setCopyHint("已复制 trace_id");
    } catch {
      setCopyHint("复制失败");
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-ink/30 p-4" role="dialog" aria-modal="true">
      <div className="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-xl border border-line bg-surface shadow-overlay">
        <header className="flex shrink-0 items-center justify-between gap-3 border-b border-line-soft px-5 py-4">
          <div>
            <h3 className="text-base font-semibold text-ink">调用详情</h3>
            {detail && (
              <p className="mt-0.5 text-xs text-ink-muted">
                {formatCallRecordTime(detail.created_at)} · {agentCallStatusLabel(detail.status)} · {agentCallRouteLabel(detail.route)}
              </p>
            )}
          </div>
          <button type="button" className="btn-icon" onClick={onClose} aria-label="关闭">
            ×
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4 text-sm">
          {loading && <p className="text-ink-muted">加载中…</p>}
          {error && <p className="text-red-600">{error}</p>}
          {detail && (
            <dl className="space-y-4">
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <dt className="text-ink-muted">操作者</dt>
                  <dd className="mt-1 text-ink">{detail.actor_username ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-ink-muted">耗时</dt>
                  <dd className="mt-1 tabular-nums text-ink">{detail.latency_ms} ms</dd>
                </div>
                <div>
                  <dt className="text-ink-muted">Token</dt>
                  <dd className="mt-1 tabular-nums text-ink">
                    {detail.prompt_tokens + detail.completion_tokens > 0
                      ? `${detail.prompt_tokens} / ${detail.completion_tokens}`
                      : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-ink-muted">步骤 / 工具</dt>
                  <dd className="mt-1 tabular-nums text-ink">
                    {detail.step_count} / {detail.tool_call_count}
                  </dd>
                </div>
              </div>

              <div>
                <dt className="text-xs text-ink-muted">会话 ID</dt>
                <dd className="mt-1 break-all font-mono text-xs text-ink">{detail.conversation_id ?? "—"}</dd>
              </div>

              <div>
                <dt className="text-xs text-ink-muted">trace_id</dt>
                <dd className="mt-1 flex flex-wrap items-center gap-2">
                  <span className="break-all font-mono text-xs text-ink">{detail.trace_id ?? "—"}</span>
                  {detail.trace_id && (
                    <button type="button" className="btn-xs-outline" onClick={() => void onCopyTrace()}>
                      复制
                    </button>
                  )}
                  {copyHint && <span className="text-xs text-ink-faint">{copyHint}</span>}
                </dd>
              </div>

              <div>
                <dt className="text-xs text-ink-muted">用户输入</dt>
                <dd className="mt-1 whitespace-pre-wrap rounded-lg bg-surface-muted px-3 py-2 text-ink">{detail.query_preview || "—"}</dd>
              </div>

              <div>
                <dt className="text-xs text-ink-muted">助手回复</dt>
                <dd className="mt-1 whitespace-pre-wrap rounded-lg bg-surface-muted px-3 py-2 text-ink">{detail.answer_preview || "—"}</dd>
              </div>

              {detail.error_message && (
                <div>
                  <dt className="text-xs text-ink-muted">错误</dt>
                  <dd className="mt-1 rounded-lg bg-red-50 px-3 py-2 text-red-700">{detail.error_message}</dd>
                </div>
              )}

              {detail.steps_summary && detail.steps_summary.length > 0 && (
                <div>
                  <dt className="mb-2 text-xs text-ink-muted">步骤摘要</dt>
                  <dd>
                    <ol className="space-y-1 text-xs text-ink-muted">
                      {detail.steps_summary.map((step, index) => (
                        <li key={`${step.type}-${index}`} className="rounded-md border border-line-soft px-3 py-2">
                          <span className="font-medium text-ink">{String(step.label ?? step.type)}</span>
                          <span className="ml-2 text-ink-faint">{String(step.type)}</span>
                        </li>
                      ))}
                    </ol>
                  </dd>
                </div>
              )}

              {detail.related_tool_logs && detail.related_tool_logs.length > 0 && (
                <div>
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <p className="text-xs text-ink-muted">关联工具调用</p>
                    <Link href="/workbench/tools" className="text-xs text-brand hover:underline">
                      打开工具页
                    </Link>
                  </div>
                  <dd>
                    <ul className="space-y-2 text-xs">
                      {detail.related_tool_logs.map((log) => (
                        <li key={log.id} className="rounded-md border border-line-soft px-3 py-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium text-ink">{log.tool_slug}</span>
                            <span className="badge bg-surface-muted text-ink-muted">{log.status}</span>
                            <span className="tabular-nums text-ink-faint">{log.latency_ms} ms</span>
                          </div>
                          {log.error_message && <p className="mt-1 text-red-600">{log.error_message}</p>}
                        </li>
                      ))}
                    </ul>
                  </dd>
                </div>
              )}

              {detail.related_hook_logs && detail.related_hook_logs.length > 0 && (
                <div>
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <p className="text-xs text-ink-muted">关联 Hook 执行</p>
                    <Link href="/workbench/hooks" className="text-xs text-brand hover:underline">
                      打开钩子页
                    </Link>
                  </div>
                  <dd>
                    <ul className="space-y-2 text-xs">
                      {detail.related_hook_logs.map((log) => (
                        <li key={log.id} className="rounded-md border border-line-soft px-3 py-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium text-ink">{hookTriggerLabel(log.trigger)}</span>
                            <span className="badge bg-surface-muted text-ink-muted">{log.status}</span>
                            {log.duration_ms != null && <span className="tabular-nums text-ink-faint">{log.duration_ms} ms</span>}
                          </div>
                          {log.error_message && <p className="mt-1 text-red-600">{log.error_message}</p>}
                        </li>
                      ))}
                    </ul>
                  </dd>
                </div>
              )}
            </dl>
          )}
        </div>

        <footer className="flex shrink-0 justify-end gap-2 border-t border-line-soft px-5 py-3">
          {(canOpenTraceLocal || canOpenTraceFromServer) && detail?.conversation_id && (
            <button
              type="button"
              className="btn-sm-outline"
              onClick={() => {
                if (canOpenTraceLocal) {
                  onOpenTrace?.();
                } else if (onOpenTraceFromRecord) {
                  void onOpenTraceFromRecord(detail.conversation_id!);
                }
                onClose();
              }}
            >
              在 Trace 中打开
            </button>
          )}
          <button type="button" className="btn-sm-primary" onClick={onClose}>
            关闭
          </button>
        </footer>
      </div>
    </div>
  );
}
