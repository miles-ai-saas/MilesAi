"use client";

import { AgentChatLeftSidebar } from "@/features/agents/components/AgentChatLeftSidebar";
import { AgentWorkbenchOverlay } from "@/features/agents/components/AgentWorkbenchOverlay";
import { AgentWorkbenchSidebar } from "@/features/agents/components/AgentWorkbenchSidebar";
import { AgentsChatMainColumn } from "@/features/agents/components/AgentsChatMainColumn";
import type { AgentsChatPageVm } from "@/features/agents/hooks/use-agents-chat-page";

type Props = {
  vm: AgentsChatPageVm;
};

export function AgentsChatLayout({ vm }: Props) {
  const {
    list,
    selectedAgent,
    conversationId,
    messages,
    sessionTitle,
    workbenchTab,
    panelOpen,
    leftCollapsed,
    rightCollapsed,
    agentsColumnCompact,
    focusMode,
    leftDrawerOpen,
    setLeftDrawerOpen,
    selected,
    leftSidebarProps,
    selectedTurnIndex,
    setSelectedTurnIndex,
    confirmDialog,
    persistSidebar,
    setLeftCollapsed,
    setRightCollapsed,
    setAgentsColumnCompact,
    setFocusMode,
    onTabChange,
    openTraceLatest,
    closePanel,
    handleAgentRenamed,
  } = vm;

  return (
    <div className="relative flex h-[calc(100vh-3.5rem)] min-h-0">
      {!focusMode ? (
        <div className="hidden h-full shrink-0 lg:block">
          <AgentChatLeftSidebar
            {...leftSidebarProps}
            hideCollapseButton={panelOpen}
            onToggleCollapse={() => {
              const next = !leftCollapsed;
              setLeftCollapsed(next);
              persistSidebar({ leftCollapsed: next });
            }}
          />
        </div>
      ) : null}

      {leftDrawerOpen && !focusMode ? (
        <>
          <button type="button" className="fixed inset-0 z-40 bg-black/30 lg:hidden" aria-label="关闭侧栏" onClick={() => setLeftDrawerOpen(false)} />
          <div className="fixed inset-y-0 left-0 z-50 h-full shadow-xl lg:hidden">
            <AgentChatLeftSidebar {...leftSidebarProps} hideCollapseButton onToggleCollapse={() => setLeftDrawerOpen(false)} />
          </div>
        </>
      ) : null}

      <AgentsChatMainColumn {...vm} />

      {!focusMode ? (
        <div className="hidden h-full shrink-0 lg:block">
          <AgentWorkbenchSidebar
            agent={selected ?? null}
            activeTab={workbenchTab}
            panelOpen={panelOpen}
            collapsed={rightCollapsed}
            hideCollapseButton={panelOpen}
            onToggleCollapse={() => {
              const next = !rightCollapsed;
              setRightCollapsed(next);
              persistSidebar({ rightCollapsed: next });
            }}
            onTabChange={onTabChange}
            onAgentRenamed={handleAgentRenamed}
          />
        </div>
      ) : null}

      {focusMode ? (
        <div className="pointer-events-none fixed bottom-4 right-4 z-30 flex flex-col gap-2 sm:flex-row">
          <button type="button" className="btn-sm-outline pointer-events-auto shadow-md" onClick={openTraceLatest}>
            Trace
          </button>
          <button
            type="button"
            className="btn-sm-outline pointer-events-auto shadow-md"
            onClick={() => {
              setFocusMode(false);
              persistSidebar({ focusMode: false });
            }}
          >
            退出专注
          </button>
        </div>
      ) : null}

      <AgentWorkbenchOverlay
        open={panelOpen}
        agent={selected ?? null}
        agentId={selectedAgent || null}
        activeTab={workbenchTab}
        rightRailCollapsed={rightCollapsed}
        chatMessages={messages}
        traceTurnIndex={selectedTurnIndex}
        onTraceTurnIndexChange={setSelectedTurnIndex}
        onClose={closePanel}
        onSaved={() => list.reload()}
      />
      {confirmDialog}
    </div>
  );
}
