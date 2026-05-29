"use client";

import type { ChatSession } from "@/lib/chat-sessions";

export function AgentChatSessionColumnCompact({
  selectedAgentId,
  sessions,
  activeSessionId,
  onNewSession,
  onSelectSession,
}: {
  selectedAgentId: string;
  sessions: ChatSession[];
  activeSessionId: string | null;
  onNewSession: () => void;
  onSelectSession: (id: string) => void;
}) {
  return (
    <div className="flex flex-col items-center gap-2 border-t border-line-soft py-2">
      <button
        type="button"
        title="新会话"
        disabled={!selectedAgentId}
        onClick={onNewSession}
        className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand text-lg text-brand-foreground disabled:opacity-40"
      >
        +
      </button>
      <ul className="flex max-h-24 flex-col items-center gap-1 overflow-y-auto">
        {sessions.slice(0, 8).map((s) => (
          <li key={s.id}>
            <button
              type="button"
              title={s.title}
              onClick={() => onSelectSession(s.id)}
              className={`h-2 w-2 rounded-full transition ${s.id === activeSessionId ? "bg-brand" : "bg-line hover:bg-brand/50"}`}
            />
          </li>
        ))}
      </ul>
    </div>
  );
}
