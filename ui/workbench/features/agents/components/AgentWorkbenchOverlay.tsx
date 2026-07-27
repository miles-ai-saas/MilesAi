"use client";

import { AgentArchitecturePanel } from "@/features/agents/components/AgentArchitecturePanel";
import { AgentApiPanel } from "@/features/agents/components/AgentApiPanel";
import { AgentCallRecordsPanel } from "@/features/agents/components/AgentCallRecordsPanel";
import { AgentSchedulePanel } from "@/features/agents/components/AgentSchedulePanel";
import { AgentStatsPanel } from "@/features/agents/components/AgentStatsPanel";
import { AgentTracePanel } from "@/features/agents/components/AgentTracePanel";
import { AgentWorkbenchPanel } from "@/features/agents/components/AgentWorkbenchPanel";
import { AGENT_WORKBENCH_TABS, type AgentWorkbenchTab } from "@/features/agents/hooks/use-agents-chat-layout";
import { useAgentCallRecordsPanel } from "@/features/agents/hooks/use-agent-call-records-panel";
import type { ChatMessage } from "@/features/agents/lib/chat-sessions";
import type { Agent } from "@/lib/types";

type Props = {
  open: boolean;
  agent: Agent | null;
  agentId: string | null;
  conversationId?: string;
  activeTab: AgentWorkbenchTab;
  rightRailCollapsed: boolean;
  chatMessages: ChatMessage[];
  traceTurnIndex: number;
  onTraceTurnIndexChange: (index: number) => void;
  onOpenTrace?: () => void;
  onOpenTraceFromRecord?: (sessionId: string) => void | Promise<void>;
  onClose: () => void;
  onSaved?: () => void;
};

export function AgentWorkbenchOverlay({
  open,
  agent,
  agentId,
  conversationId,
  activeTab,
  rightRailCollapsed,
  chatMessages,
  traceTurnIndex,
  onTraceTurnIndexChange,
  onOpenTrace,
  onOpenTraceFromRecord,
  onClose,
  onSaved,
}: Props) {
  const callRecordsVm = useAgentCallRecordsPanel(
    agentId ?? "",
    conversationId,
    open && activeTab === "call_records",
  );

  if (!open) return null;

  const tabMeta = AGENT_WORKBENCH_TABS.find((t) => t.id === activeTab);
  const title = tabMeta?.label ?? "工作台";

  const subtitle =
    activeTab === "config"
      ? "模型、知识库、子智能体与工作流"
      : activeTab === "trace"
        ? "当前会话执行步骤 JSON 与 trace_id"
        : activeTab === "architecture"
          ? "执行路径与编排预览"
          : activeTab === "schedule"
            ? "按计划自动向智能体发送消息"
            : activeTab === "stats"
              ? "会话、用户与消息趋势"
              : activeTab === "call_records"
                ? "智能体对话调用流水"
                : activeTab === "api"
                  ? "对接文档与调试 Token"
                  : "功能开发中";

  return (
    <div
      className={`absolute inset-0 right-0 z-50 flex flex-col bg-surface transition-[right] duration-200 ease-out ${
        rightRailCollapsed ? "lg:right-12" : "lg:right-40"
      }`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="workbench-overlay-title"
    >
      <header className="flex shrink-0 items-center justify-between gap-4 border-b border-line-soft bg-surface-subtle/80 px-6 py-3">
        <div className="min-w-0">
          <h2 id="workbench-overlay-title" className="truncate text-base font-semibold text-ink">
            {agent ? (
              <>
                <span className="text-ink-muted">{title}</span>
                <span className="mx-2 text-ink-faint">·</span>
                {agent.name}
              </>
            ) : (
              title
            )}
          </h2>
          <p className="mt-0.5 text-xs text-ink-muted">{subtitle}</p>
        </div>
        <button
          type="button"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-ink-faint transition hover:bg-surface-muted hover:text-ink"
          onClick={onClose}
          aria-label="关闭"
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </header>
      <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden bg-surface">
        {activeTab === "trace" ? (
          <AgentTracePanel messages={chatMessages} selectedTurnIndex={traceTurnIndex} onSelectTurnIndex={onTraceTurnIndexChange} />
        ) : activeTab === "stats" && agentId ? (
          <AgentStatsPanel agentId={agentId} />
        ) : activeTab === "schedule" && agentId ? (
          <AgentSchedulePanel agentId={agentId} />
        ) : activeTab === "architecture" && agentId ? (
          <AgentArchitecturePanel agentId={agentId} agentName={agent?.name} />
        ) : activeTab === "api" && agentId ? (
          <AgentApiPanel agentId={agentId} />
        ) : activeTab === "call_records" && agentId ? (
          <AgentCallRecordsPanel
            agentId={agentId}
            conversationId={conversationId}
            vm={callRecordsVm}
            onOpenTrace={onOpenTrace}
            onOpenTraceFromRecord={onOpenTraceFromRecord}
          />
        ) : (
          <AgentWorkbenchPanel agentId={agentId} agentName={agent?.name} activeTab={activeTab} onSaved={onSaved} />
        )}
      </div>
    </div>
  );
}
