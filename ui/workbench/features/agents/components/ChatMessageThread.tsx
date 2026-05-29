"use client";

/** 对话消息区（链路 §5）：渲染消息 + `AgentExecutionTimeline`（steps）。 */

import { AgentExecutionSkeleton, AgentExecutionTimeline } from "@/features/agents/components/AgentExecutionTimeline";
import { ChatArtifactMedia } from "@/features/agents/components/ChatArtifactMedia";
import type { ChatMessage } from "@/features/agents/lib/chat-sessions";
import { turnIndexForMessageIndex } from "@/features/agents/lib/agent-trace";
import type { PendingToolCall } from "@/lib/types";
import type { ReactNode } from "react";

type Props = {
  messages: ChatMessage[];
  chatting: boolean;
  pendingTool?: PendingToolCall | null;
  onConfirmPendingTool?: () => void;
  confirmPendingToolDisabled?: boolean;
  /** 覆盖默认「思考中…」 */
  chattingStatusLabel?: string | null;
  /** 异步生成进度（显示在最后一条助手消息下方或流式骨架下方） */
  generativeStatus?: ReactNode;
  /** 点击助手消息打开 Trace（传入轮次下标） */
  onOpenTraceTurn?: (turnIndex: number) => void;
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
  chattingStatusLabel,
  generativeStatus,
  onOpenTraceTurn,
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
        <p className="mt-1 text-xs text-ink-faint">支持直连、RAG、流程与多模态；助手卡片可点「Trace」查看执行步骤</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {messages.map((msg, i) => {
        const traceTurn = msg.role === "assistant" ? turnIndexForMessageIndex(messages, i) : null;
        const showTraceBtn = traceTurn != null && onOpenTraceTurn && ((msg.steps?.length ?? 0) > 0 || Boolean(msg.traceId));

        return (
          <div key={`${i}-${msg.role}`}>
            {msg.role === "user" ? (
              <div className="flex justify-end">
                <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-brand px-4 py-2.5 text-sm text-brand-foreground">
                  {msg.media && msg.media.length > 0 && (
                    <div className="mb-2 flex flex-wrap justify-end gap-2">
                      {msg.media.map((m) =>
                        m.preview_url ? (
                          <img
                            key={m.attachment_id}
                            src={m.preview_url}
                            alt={m.filename ?? "附图"}
                            className="max-h-32 max-w-[140px] rounded-lg object-cover"
                          />
                        ) : null,
                      )}
                    </div>
                  )}
                  {msg.content ? <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p> : null}
                </div>
              </div>
            ) : (
              <div className="card p-4">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <p className="text-xs font-medium text-brand">助手</p>
                  {showTraceBtn ? (
                    <button type="button" className="btn-sm-ghost text-[10px] text-ink-muted" onClick={() => onOpenTraceTurn(traceTurn)}>
                      Trace
                    </button>
                  ) : null}
                </div>
                {msg.steps && msg.steps.length > 0 && (
                  <AgentExecutionTimeline
                    steps={msg.steps}
                    pendingTool={i === lastAssistantIndex && pendingTool && hasPendingConfirmationStep(msg.steps) ? pendingTool : null}
                    onConfirmTool={i === lastAssistantIndex && pendingTool && hasPendingConfirmationStep(msg.steps) ? onConfirmPendingTool : undefined}
                    confirmToolDisabled={confirmPendingToolDisabled}
                  />
                )}
                {msg.artifacts && msg.artifacts.length > 0 && (
                  <div className="mb-3 flex flex-wrap gap-2">
                    {msg.artifacts.map((a) => (
                      <ChatArtifactMedia key={a.attachment_id} kind={a.kind} attachmentId={a.attachment_id} mimeType={a.mime_type} caption={a.caption} />
                    ))}
                  </div>
                )}
                <div className="whitespace-pre-wrap text-sm leading-relaxed text-ink">{msg.content}</div>
                {i === lastAssistantIndex && generativeStatus ? <div className="mt-3">{generativeStatus}</div> : null}
              </div>
            )}
          </div>
        );
      })}
      {chatting && (
        <div className="card p-4">
          <p className="mb-2 text-xs font-medium text-brand">助手</p>
          <AgentExecutionSkeleton />
          <p className="mt-1 text-sm text-ink-muted">{chattingStatusLabel ?? "思考中…"}</p>
          {generativeStatus ? <div className="mt-3">{generativeStatus}</div> : null}
        </div>
      )}
      {!chatting && lastAssistantIndex < 0 && generativeStatus ? <div>{generativeStatus}</div> : null}
    </div>
  );
}
