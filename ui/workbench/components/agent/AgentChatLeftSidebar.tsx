"use client";

/** 对话页左侧：智能体列表与会话切换（链路 §5）。 */
import { useEffect, useRef } from "react";
import { AgentChatSessionPanel } from "@/components/agent/AgentChatSessionPanel";
import {
  CHAT_AGENT_COLUMN,
  CHAT_AGENT_COLUMN_COMPACT,
  CHAT_LEFT_SIDEBAR_COLLAPSED,
  CHAT_LEFT_SIDEBAR_EXPANDED,
  CHAT_SESSION_COLUMN,
} from "@/components/agent/chat-sidebar-layout";
import { SidebarCollapseButton } from "@/components/agent/SidebarCollapseButton";
import type { ChatSession } from "@/lib/chat-sessions";
import { agentModeLabel } from "@/lib/agent-utils";
import type { Agent } from "@/lib/types";

type Props = {
  agents: Agent[];
  total: number;
  selectedAgentId: string;
  sessions: ChatSession[];
  activeSessionId: string | null;
  collapsed: boolean;
  /** 已选智能体时智能体列仅头像，会话列加宽 */
  agentsColumnCompact?: boolean;
  /** 右侧工作台面板打开时隐藏折叠钮 */
  hideCollapseButton?: boolean;
  hasMoreAgents: boolean;
  loadingMoreAgents: boolean;
  onLoadMoreAgents: () => void;
  onToggleCollapse: () => void;
  onSelectAgent: (id: string) => void;
  onNewSession: () => void;
  onSelectSession: (id: string) => void;
  onRenameSession: (sessionId: string, title: string) => void;
  onDeleteSession: (id: string) => void;
};

function agentInitial(name: string) {
  return (name.trim()[0] ?? "?").toUpperCase();
}

function AgentColumn({
  agents,
  total,
  selectedAgentId,
  compact,
  hasMore,
  loadingMore,
  onLoadMore,
  onSelectAgent,
}: {
  agents: Agent[];
  total: number;
  selectedAgentId: string;
  compact: boolean;
  hasMore: boolean;
  loadingMore: boolean;
  onLoadMore: () => void;
  onSelectAgent: (id: string) => void;
}) {
  const scrollRef = useRef<HTMLUListElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = scrollRef.current;
    const sentinel = sentinelRef.current;
    if (!root || !sentinel) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && hasMore && !loadingMore) {
          onLoadMore();
        }
      },
      { root, rootMargin: "64px", threshold: 0 },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, loadingMore, onLoadMore, agents.length]);

  const listContent = agents.map((a) => (
    <li key={a.id}>
      {compact ? (
        <button
          type="button"
          title={`${a.name} · ${agentModeLabel(a)}`}
          onClick={() => onSelectAgent(a.id)}
          className={`flex h-9 w-9 items-center justify-center rounded-lg text-sm font-medium transition ${
            selectedAgentId === a.id
              ? "bg-brand text-brand-foreground shadow-sm"
              : "text-ink-muted hover:bg-brand-light hover:text-brand"
          }`}
        >
          {agentInitial(a.name)}
        </button>
      ) : (
        <button
          type="button"
          onClick={() => onSelectAgent(a.id)}
          className={`mb-1 w-full rounded-lg border px-2.5 py-2 text-left text-sm transition ${
            selectedAgentId === a.id
              ? "border-brand/30 bg-brand-light"
              : "border-transparent hover:border-line hover:bg-brand-light/40"
          }`}
        >
          <p className="truncate font-medium text-ink">{a.name}</p>
          <p className="mt-0.5 truncate text-xs text-ink-muted">{agentModeLabel(a)}</p>
        </button>
      )}
    </li>
  ));

  const loadTail =
    hasMore || loadingMore ? (
      <li className={compact ? "py-1" : "py-2"}>
        <div
          ref={sentinelRef}
          className={`flex items-center justify-center text-[10px] text-ink-faint ${
            compact ? "min-h-6" : "min-h-8"
          }`}
        >
          {loadingMore ? "加载中…" : ""}
        </div>
      </li>
    ) : null;

  if (compact) {
    return (
      <ul ref={scrollRef} className="flex min-h-0 flex-1 flex-col items-center gap-1 overflow-y-auto py-2">
        {listContent}
        {loadTail}
      </ul>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="shrink-0 border-b border-line-soft px-3 py-2.5">
        <p className="text-xs font-medium text-ink">智能体</p>
        <p className="mt-0.5 text-[10px] text-ink-faint">
          共 {total} 个{agents.length < total ? ` · 已加载 ${agents.length}` : ""}
        </p>
      </div>
      <ul ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto p-2">
        {listContent}
        {loadTail}
      </ul>
    </div>
  );
}

function SessionColumnCompact({
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
              className={`h-2 w-2 rounded-full transition ${
                s.id === activeSessionId ? "bg-brand" : "bg-line hover:bg-brand/50"
              }`}
            />
          </li>
        ))}
      </ul>
    </div>
  );
}

export function AgentChatLeftSidebar({
  agents,
  total,
  selectedAgentId,
  sessions,
  activeSessionId,
  collapsed,
  agentsColumnCompact = false,
  hideCollapseButton,
  hasMoreAgents,
  loadingMoreAgents,
  onLoadMoreAgents,
  onToggleCollapse,
  onSelectAgent,
  onNewSession,
  onSelectSession,
  onRenameSession,
  onDeleteSession,
}: Props) {
  const agentColumnProps = {
    agents,
    total,
    selectedAgentId,
    hasMore: hasMoreAgents,
    loadingMore: loadingMoreAgents,
    onLoadMore: onLoadMoreAgents,
    onSelectAgent,
  };

  return (
    <aside
      className="relative flex h-full shrink-0 flex-col overflow-hidden border-r border-line bg-surface transition-[width] duration-200 ease-out"
      style={{ width: collapsed ? CHAT_LEFT_SIDEBAR_COLLAPSED : CHAT_LEFT_SIDEBAR_EXPANDED }}
    >
      <SidebarCollapseButton
        side="left"
        collapsed={collapsed}
        onToggle={onToggleCollapse}
        hidden={hideCollapseButton}
      />

      {collapsed ? (
        <div className="flex min-h-0 flex-1 flex-col">
          <AgentColumn {...agentColumnProps} compact />
          <SessionColumnCompact
            selectedAgentId={selectedAgentId}
            sessions={sessions}
            activeSessionId={activeSessionId}
            onNewSession={onNewSession}
            onSelectSession={onSelectSession}
          />
        </div>
      ) : (
        <div className="flex min-h-0 flex-1">
          <div
            className="flex min-h-0 shrink-0 flex-col border-r border-line-soft"
            style={{
              width: agentsColumnCompact && selectedAgentId ? CHAT_AGENT_COLUMN_COMPACT : CHAT_AGENT_COLUMN,
            }}
          >
            <AgentColumn
              {...agentColumnProps}
              compact={Boolean(agentsColumnCompact && selectedAgentId)}
            />
          </div>
          <div
            className="flex min-h-0 min-w-0 flex-1 flex-col"
            style={
              agentsColumnCompact && selectedAgentId
                ? undefined
                : { width: CHAT_SESSION_COLUMN, flex: "none" }
            }
          >
            <div className="shrink-0 border-b border-line-soft px-3 py-2.5">
              <p className="text-xs font-medium text-ink">会话</p>
              <p className="mt-0.5 truncate text-[10px] text-ink-faint">
                {selectedAgentId ? "当前智能体的对话记录" : "选择智能体后显示"}
              </p>
            </div>
            <AgentChatSessionPanel
              agentSelected={Boolean(selectedAgentId)}
              sessions={sessions}
              activeSessionId={activeSessionId}
              onNewSession={onNewSession}
              onSelectSession={onSelectSession}
              onRenameSession={onRenameSession}
              onDeleteSession={onDeleteSession}
            />
          </div>
        </div>
      )}
    </aside>
  );
}
