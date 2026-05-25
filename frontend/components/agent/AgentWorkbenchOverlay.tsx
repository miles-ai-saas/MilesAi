"use client";

import { AGENT_WORKBENCH_TABS, type AgentWorkbenchTab } from "@/components/agent/agent-workbench-tabs";
import { AgentTracePanel } from "@/components/agent/AgentTracePanel";
import { AgentWorkbenchPanel } from "@/components/agent/AgentWorkbenchPanel";
import type { ChatMessage } from "@/lib/chat-sessions";
import type { Agent } from "@/lib/types";

type Props = {
  open: boolean;
  agent: Agent | null;
  agentId: string | null;
  activeTab: AgentWorkbenchTab;
  rightRailCollapsed: boolean;
  chatMessages: ChatMessage[];
  traceTurnIndex: number;
  onTraceTurnIndexChange: (index: number) => void;
  onClose: () => void;
  onSaved?: () => void;
};

export function AgentWorkbenchOverlay({
  open,
  agent,
  agentId,
  activeTab,
  rightRailCollapsed,
  chatMessages,
  traceTurnIndex,
  onTraceTurnIndexChange,
  onClose,
  onSaved,
}: Props) {
  if (!open) return null;

  const tabMeta = AGENT_WORKBENCH_TABS.find((t) => t.id === activeTab);
  const title = tabMeta?.label ?? "工作台";

  const subtitle =
    activeTab === "config"
      ? "模型、知识库、子智能体与工作流"
      : activeTab === "trace"
        ? "当前会话执行步骤 JSON 与 trace_id"
        : activeTab === "architecture"
          ? "编排流程与画布"
          : "功能开发中";

  return (
    <div
      className={`absolute inset-0 right-0 z-20 flex flex-col bg-surface transition-[right] duration-200 ease-out ${
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
      <div className="flex min-h-0 flex-1 flex-col bg-surface">
        {activeTab === "trace" ? (
          <AgentTracePanel
            messages={chatMessages}
            selectedTurnIndex={traceTurnIndex}
            onSelectTurnIndex={onTraceTurnIndexChange}
          />
        ) : (
          <AgentWorkbenchPanel agentId={agentId} activeTab={activeTab} onSaved={onSaved} />
        )}
      </div>
    </div>
  );
}
