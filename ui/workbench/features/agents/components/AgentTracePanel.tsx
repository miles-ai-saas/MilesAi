"use client";

/** Trace 侧栏（链路 §5）：`agent-trace` 轮次 + steps 明细。 */

import { useEffect, useMemo, useState } from "react";
import { copyText, defaultTraceTurnIndex, listTraceTurns } from "@/lib/agent-trace";
import type { ChatMessage } from "@/lib/chat-sessions";

type Props = {
  messages: ChatMessage[];
  selectedTurnIndex: number;
  onSelectTurnIndex: (index: number) => void;
};

export function AgentTracePanel({ messages, selectedTurnIndex, onSelectTurnIndex }: Props) {
  const turns = useMemo(() => listTraceTurns(messages), [messages]);
  const selected = turns[selectedTurnIndex] ?? null;
  const [copyHint, setCopyHint] = useState("");

  useEffect(() => {
    if (!copyHint) return;
    const t = window.setTimeout(() => setCopyHint(""), 2000);
    return () => window.clearTimeout(t);
  }, [copyHint]);

  const onCopy = async (label: string, text: string) => {
    const ok = await copyText(text);
    setCopyHint(ok ? `已复制${label}` : "复制失败");
  };

  if (!turns.length) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center">
        <p className="text-sm text-ink-muted">当前会话尚无助手回复</p>
        <p className="text-xs text-ink-faint">发送消息后，可在此查看执行步骤 JSON 与 trace_id</p>
      </div>
    );
  }

  const payload = selected
    ? {
        trace_id: selected.traceId ?? null,
        user_query: selected.userQuery,
        steps: selected.steps,
        step_count: selected.steps.length,
      }
    : null;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="shrink-0 space-y-3 border-b border-line-soft px-6 py-4">
        <div>
          <label className="mb-1 block text-xs font-medium text-ink-muted">选择回复</label>
          <select className="input-field text-xs" value={selectedTurnIndex} onChange={(e) => onSelectTurnIndex(Number(e.target.value))}>
            {turns.map((t) => (
              <option key={t.messageIndex} value={t.turnIndex}>
                #{t.turnIndex + 1} · {t.userQuery.slice(0, 36) || "（无用户问题）"}
                {t.userQuery.length > 36 ? "…" : ""}
              </option>
            ))}
          </select>
        </div>

        <div className="rounded-lg border border-line-soft bg-surface-muted/60 px-3 py-2.5">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <p className="text-[10px] font-medium uppercase tracking-wide text-ink-faint">X-Trace-Id</p>
              <p className="mt-0.5 break-all font-mono text-xs text-ink">{selected?.traceId ?? "—"}</p>
            </div>
            <button
              type="button"
              className="btn-sm-outline shrink-0 px-2 py-1 text-[11px]"
              disabled={!selected?.traceId}
              onClick={() => void onCopy(" trace_id", selected?.traceId ?? "")}
            >
              复制
            </button>
          </div>
          <p className="mt-2 text-[11px] text-ink-muted">
            步骤数 {selected?.steps.length ?? 0}
            {selected?.steps.length ? "" : " · 该轮无 steps 记录"}
          </p>
        </div>

        {copyHint ? <p className="text-xs text-brand">{copyHint}</p> : null}
      </div>

      <div className="flex min-h-0 flex-1 flex-col px-6 py-4">
        <div className="mb-2 flex items-center justify-between gap-2">
          <h3 className="text-xs font-medium text-ink">执行步骤 JSON</h3>
          <button
            type="button"
            className="btn-sm-ghost px-2 py-1 text-[11px]"
            disabled={!payload}
            onClick={() => void onCopy(" JSON", JSON.stringify(payload, null, 2))}
          >
            复制全部
          </button>
        </div>
        <pre className="min-h-0 flex-1 overflow-auto rounded-lg border border-line-soft bg-surface-muted p-3 font-mono text-[11px] leading-relaxed text-ink">
          {JSON.stringify(payload, null, 2)}
        </pre>
      </div>
    </div>
  );
}

export function useTraceTurnSelection(messages: ChatMessage[], sessionKey?: string) {
  const turns = useMemo(() => listTraceTurns(messages), [messages]);
  const [selectedTurnIndex, setSelectedTurnIndex] = useState(0);

  useEffect(() => {
    setSelectedTurnIndex(defaultTraceTurnIndex(turns));
  }, [turns.length, sessionKey]);

  return { turns, selectedTurnIndex, setSelectedTurnIndex };
}
