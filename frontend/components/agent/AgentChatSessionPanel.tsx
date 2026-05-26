"use client";

/** 对话页会话列表（链路 §5，数据来自 chat-sessions）。 */
import { groupSessionsByDate, type ChatSession } from "@/lib/chat-sessions";

type Props = {
  agentSelected: boolean;
  sessions: ChatSession[];
  activeSessionId: string | null;
  onNewSession: () => void;
  onSelectSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
};

function formatTime(ts: number) {
  return new Date(ts).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

export function AgentChatSessionPanel({
  agentSelected,
  sessions,
  activeSessionId,
  onNewSession,
  onSelectSession,
  onDeleteSession,
}: Props) {
  if (!agentSelected) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center px-4 py-8 text-center text-xs text-ink-muted">
        请先在左侧选择要对话的智能体
      </div>
    );
  }

  const groups = groupSessionsByDate(sessions);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="shrink-0 border-b border-line-soft p-3">
        <button type="button" className="btn-primary w-full text-xs" onClick={onNewSession}>
          + 新会话
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {groups.length === 0 ? (
          <p className="px-2 py-6 text-center text-xs text-ink-faint">暂无会话，点击上方创建</p>
        ) : (
          groups.map((group) => (
            <div key={group.label} className="mb-3">
              <p className="mb-1 px-2 text-[10px] font-medium uppercase tracking-wider text-ink-faint">
                {group.label}
              </p>
              <ul className="space-y-0.5">
                {group.sessions.map((s) => {
                  const active = s.id === activeSessionId;
                  const preview =
                    s.messages.find((m) => m.role === "user")?.content?.slice(0, 40) ??
                    "暂无消息";
                  return (
                    <li key={s.id}>
                      <div
                        className={`group flex items-start gap-1 rounded-lg border px-2.5 py-2 transition ${
                          active
                            ? "border-brand/30 bg-brand-light"
                            : "border-transparent hover:border-line hover:bg-brand-light/30"
                        }`}
                      >
                        <button
                          type="button"
                          className="min-w-0 flex-1 text-left"
                          onClick={() => onSelectSession(s.id)}
                        >
                          <p className="truncate text-sm font-medium text-ink">{s.title}</p>
                          <p className="mt-0.5 truncate text-[11px] text-ink-muted">{preview}</p>
                          <p className="mt-0.5 text-[10px] text-ink-faint">
                            {formatTime(s.updatedAt)}
                            {s.messages.length > 0
                              ? ` · ${Math.ceil(s.messages.length / 2)} 轮`
                              : ""}
                          </p>
                        </button>
                        <button
                          type="button"
                          title="删除会话"
                          className="shrink-0 rounded p-1 text-ink-faint opacity-0 transition hover:bg-surface hover:text-red-600 group-hover:opacity-100"
                          onClick={() => onDeleteSession(s.id)}
                        >
                          <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path strokeLinecap="round" d="M6 6l12 12M18 6L6 18" />
                          </svg>
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
