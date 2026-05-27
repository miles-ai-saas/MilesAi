"use client";

/** 对话调试台顶栏：会话为主标题、状态芯片与布局控制。 */
import Link from "next/link";
import { AgentRenameInline } from "@/components/agent/AgentRenameInline";
import { ChatSessionRenameInline } from "@/components/agent/ChatSessionRenameInline";
import type { Agent } from "@/lib/types";
import { agentModeLabel } from "@/lib/agent-utils";

type Props = {
  sessionTitle: string;
  sessionRenameDisabled?: boolean;
  onSessionRename?: (title: string) => void;
  agent: Agent | null;
  onAgentRenamed?: (name: string) => void;
  wsEnabled: boolean;
  wsReady: boolean;
  lastTraceId?: string | null;
  focusMode: boolean;
  agentsColumnCompact: boolean;
  onNewSession: () => void;
  onOpenTrace: () => void;
  onToggleFocusMode: () => void;
  onToggleAgentsColumnCompact: () => void;
  onOpenLeftDrawer?: () => void;
  showLeftDrawerButton?: boolean;
};

export function AgentChatDebugHeader({
  sessionTitle,
  sessionRenameDisabled = false,
  onSessionRename,
  agent,
  onAgentRenamed,
  wsEnabled,
  wsReady,
  lastTraceId,
  focusMode,
  agentsColumnCompact,
  onNewSession,
  onOpenTrace,
  onToggleFocusMode,
  onToggleAgentsColumnCompact,
  onOpenLeftDrawer,
  showLeftDrawerButton,
}: Props) {
  const transportLabel = !wsEnabled
    ? "HTTP"
    : wsReady
      ? "WS"
      : "WS…";

  return (
    <header className="sticky top-0 z-20 shrink-0 border-b border-line bg-surface/95 backdrop-blur-sm">
      <div className="flex items-center gap-2 px-3 py-2 sm:gap-3 sm:px-4">
        {showLeftDrawerButton && onOpenLeftDrawer ? (
          <button
            type="button"
            className="btn-sm-ghost shrink-0 lg:hidden"
            aria-label="打开侧栏"
            onClick={onOpenLeftDrawer}
          >
            ☰
          </button>
        ) : null}

        <div className="min-w-0 flex-1">
          {onSessionRename && !sessionRenameDisabled ? (
            <ChatSessionRenameInline
              title={sessionTitle}
              prominent
              className="text-base sm:text-lg"
              onRename={onSessionRename}
            />
          ) : (
            <h2 className="truncate text-base font-semibold text-ink sm:text-lg" title={sessionTitle}>
              {sessionTitle}
            </h2>
          )}
          <div className="mt-0.5 flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs text-ink-muted">
            {agent ? (
              <>
                <AgentRenameInline
                  agentId={agent.id}
                  name={agent.name}
                  className="max-w-[min(100%,14rem)]"
                  onRenamed={(name) => onAgentRenamed?.(name)}
                />
                <span className="text-ink-faint">·</span>
                <span className="truncate">{agentModeLabel(agent)}</span>
              </>
            ) : (
              "请选择智能体"
            )}
          </div>
        </div>

        <div className="hidden flex-wrap items-center justify-end gap-1.5 sm:flex">
          <span
            className={`rounded-md px-2 py-0.5 font-mono text-[10px] ${
              wsEnabled && wsReady
                ? "bg-emerald-50 text-emerald-800"
                : "bg-surface-muted text-ink-faint"
            }`}
            title={wsEnabled ? "WebSocket 已连接" : "HTTP 流式"}
          >
            {transportLabel}
          </span>
          {lastTraceId ? (
            <span
              className="max-w-[8rem] truncate rounded-md bg-surface-muted px-2 py-0.5 font-mono text-[10px] text-ink-muted"
              title={lastTraceId}
            >
              trace …{lastTraceId.slice(-8)}
            </span>
          ) : null}
        </div>

        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            className="btn-sm-ghost hidden text-xs sm:inline-flex"
            title={agentsColumnCompact ? "展开智能体列表" : "收窄智能体列"}
            onClick={onToggleAgentsColumnCompact}
          >
            {agentsColumnCompact ? "智能体▸" : "智能体◂"}
          </button>
          <button type="button" className="btn-sm-ghost text-xs" onClick={onOpenTrace}>
            Trace
          </button>
          <Link href="/workbench/tasks" className="btn-sm-ghost hidden text-xs md:inline-flex">
            任务
          </Link>
          <button
            type="button"
            className="btn-sm-ghost text-xs"
            title={focusMode ? "退出专注模式" : "专注模式：隐藏侧栏"}
            onClick={onToggleFocusMode}
          >
            {focusMode ? "退出专注" : "专注"}
          </button>
          <button type="button" className="btn-sm-outline text-xs" onClick={onNewSession}>
            新会话
          </button>
        </div>
      </div>
    </header>
  );
}
