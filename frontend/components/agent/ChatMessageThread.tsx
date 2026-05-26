"use client";

/** 对话消息区（链路 §5）：渲染消息 + `AgentExecutionTimeline`（steps）。 */

import {
  AgentExecutionSkeleton,
  AgentExecutionTimeline,
} from "@/components/agent/AgentExecutionTimeline";
import type { ChatMessage } from "@/lib/chat-sessions";
import type { PendingToolCall } from "@/lib/types";

type Props = {
  messages: ChatMessage[];
  chatting: boolean;
  pendingTool?: PendingToolCall | null;
  onConfirmPendingTool?: () => void;
  confirmPendingToolDisabled?: boolean;
};

function hasPendingConfirmationStep(steps?: Record<string, unknown>[]) {
  return steps?.some((s) => s.type === "tool_confirmation_required") ?? false;
}

export function ChatMessageThread({
  messages,
  chatting,
  pendingTool,
  onConfirmPendingTool,
  confirmPendingToolDisabled,
}: Props) {
  const lastAssistantIndex = (() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i].role === "assistant") return i;
    }
    return -1;
  })();

  if (messages.length === 0 && !chatting) {
    return (
      <div className="flex h-full min-h-[200px] flex-col items-center justify-center text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-light">
          <span className="text-2xl text-brand">◇</span>
        </div>
        <p className="text-sm text-ink-muted">输入问题开始对话</p>
        <p className="mt-1 text-xs text-ink-faint">
          支持直连、RAG、流程；绑定子智能体时由规划器协同回答
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      {messages.map((msg, i) => (
        <div key={`${i}-${msg.role}`}>
          {msg.role === "user" ? (
            <div className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-brand px-4 py-2.5 text-sm text-brand-foreground">
                <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
              </div>
            </div>
          ) : (
            <div className="card p-4">
              {msg.steps && msg.steps.length > 0 && (
                <AgentExecutionTimeline
                  steps={msg.steps}
                  pendingTool={
                    i === lastAssistantIndex &&
                    pendingTool &&
                    hasPendingConfirmationStep(msg.steps)
                      ? pendingTool
                      : null
                  }
                  onConfirmTool={
                    i === lastAssistantIndex &&
                    pendingTool &&
                    hasPendingConfirmationStep(msg.steps)
                      ? onConfirmPendingTool
                      : undefined
                  }
                  confirmToolDisabled={confirmPendingToolDisabled}
                />
              )}
              <p className="mb-1 text-xs font-medium text-brand">助手</p>
              <div className="whitespace-pre-wrap text-sm leading-relaxed text-ink">{msg.content}</div>
            </div>
          )}
        </div>
      ))}
      {chatting && (
        <div className="card p-4">
          <AgentExecutionSkeleton />
          <p className="text-xs font-medium text-brand">助手</p>
          <p className="mt-1 text-sm text-ink-muted">思考中…</p>
        </div>
      )}
    </div>
  );
}
