"use client";

import type { ChatMessage } from "@/lib/chat-sessions";

type Props = {
  messages: ChatMessage[];
  chatting: boolean;
};

export function ChatMessageThread({ messages, chatting }: Props) {
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
                <details className="mb-3 text-xs text-ink-muted">
                  <summary className="cursor-pointer font-medium text-ink">
                    执行步骤（{msg.steps.length}）
                  </summary>
                  <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap font-mono text-[11px]">
                    {JSON.stringify(msg.steps, null, 2)}
                  </pre>
                </details>
              )}
              <p className="mb-1 text-xs font-medium text-brand">助手</p>
              <div className="whitespace-pre-wrap text-sm leading-relaxed text-ink">{msg.content}</div>
            </div>
          )}
        </div>
      ))}
      {chatting && (
        <div className="card flex items-center gap-2 p-4 text-sm text-ink-muted">
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-brand" />
          思考中…
        </div>
      )}
    </div>
  );
}
