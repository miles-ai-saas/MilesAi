"use client";

import { AgentChatDebugHeader } from "@/features/agents/components/AgentChatDebugHeader";
import { AgentChatComposer } from "@/features/agents/components/AgentChatComposer";
import { AgentChatLeftSidebar } from "@/features/agents/components/AgentChatLeftSidebar";
import { AgentWorkbenchOverlay } from "@/features/agents/components/AgentWorkbenchOverlay";
import { AgentWorkbenchSidebar } from "@/features/agents/components/AgentWorkbenchSidebar";
import { ChatMessageThread } from "@/features/agents/components/ChatMessageThread";
import type { AgentsChatPageVm } from "@/features/agents/hooks/use-agents-chat-page";
import { generativeToolBusyLabel } from "@/lib/generative-tool-ui";
import { useEffect, useRef } from "react";

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
    openTraceAtTurn,
    handleOpenTraceFromRecord,
    closePanel,
    handleAgentRenamed,
    wsEnabled,
    wsReady,
    lastTraceId,
    query,
    setQuery,
    imageN,
    setImageN,
    videoDuration,
    setVideoDuration,
    hasImageTool,
    hasVideoTool,
    pendingMedia,
    uploadingMedia,
    chatting,
    pendingTool,
    carriedMedia,
    chattingStatusLabel,
    generativeStatusEl,
    cancelGenerativeJobById,
    onGenerativeJobRetried,
    handleNewSession,
    handleRenameSession,
    chat,
    confirmPendingTool,
    onPickAttachments,
    removePendingMedia,
    loadMoreMessages,
    loadingMore,
    hasMore,
  } = vm;

  const chatScrollRef = useRef<HTMLDivElement>(null);
  const scrolledForConvRef = useRef<string | null>(null);

  // 切会话后等消息落入 DOM 再滚到底，避免顶部哨兵落在视口内立刻连刷接口
  useEffect(() => {
    if (!conversationId) return;
    if (scrolledForConvRef.current === conversationId) return;
    if (messages.length === 0 && !chatting) return;
    scrolledForConvRef.current = conversationId;
    const el = chatScrollRef.current;
    if (!el) return;
    const id = requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
    });
    return () => cancelAnimationFrame(id);
  }, [conversationId, messages.length, chatting]);

  return (
    <div className="relative flex h-full min-h-0 w-full flex-1 overflow-hidden">
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

      <section className="flex min-h-0 min-w-0 flex-1 flex-col bg-surface-subtle">
        <AgentChatDebugHeader
          sessionTitle={sessionTitle}
          sessionRenameDisabled={!selectedAgent || !conversationId}
          onSessionRename={(title) => handleRenameSession(conversationId, title)}
          agent={selected ?? null}
          onAgentRenamed={handleAgentRenamed}
          wsEnabled={wsEnabled}
          wsReady={wsReady}
          lastTraceId={lastTraceId}
          focusMode={focusMode}
          agentsColumnCompact={agentsColumnCompact}
          showLeftDrawerButton={!focusMode}
          onOpenLeftDrawer={() => setLeftDrawerOpen(true)}
          onNewSession={handleNewSession}
          onOpenTrace={openTraceLatest}
          onToggleFocusMode={() => {
            const next = !focusMode;
            setFocusMode(next);
            setLeftDrawerOpen(false);
            persistSidebar({ focusMode: next });
          }}
          onToggleAgentsColumnCompact={() => {
            const next = !agentsColumnCompact;
            setAgentsColumnCompact(next);
            persistSidebar({ agentsColumnCompact: next });
          }}
        />

        <div className="min-h-0 flex-1 overflow-y-auto px-3 py-4 sm:px-4" ref={chatScrollRef}>
          <div className="mx-auto w-full max-w-4xl">
            <ChatMessageThread
              messages={messages}
              chatting={chatting}
              chattingStatusLabel={chattingStatusLabel}
              pendingTool={pendingTool}
              onConfirmPendingTool={() => void confirmPendingTool()}
              confirmPendingToolDisabled={chatting}
              generativeStatus={generativeStatusEl}
              onCancelGenerativeJob={cancelGenerativeJobById}
              onGenerativeJobRetried={onGenerativeJobRetried}
              onOpenTraceTurn={openTraceAtTurn}
              onLoadMore={loadMoreMessages}
              loadingMore={loadingMore}
              hasMore={hasMore}
              conversationId={conversationId}
              agentSelected={Boolean(selectedAgent)}
              scrollContainerRef={chatScrollRef}
            />
          </div>
        </div>

        <footer className="sticky bottom-0 z-10 shrink-0 border-t border-line bg-surface/95 px-3 py-3 backdrop-blur-sm sm:px-4">
          <div className="mx-auto w-full max-w-4xl">
            <AgentChatComposer
              query={query}
              onQueryChange={setQuery}
              onSend={() => void chat()}
              onPickFiles={(files) => void onPickAttachments(files)}
              pendingMedia={pendingMedia}
              carriedMedia={carriedMedia}
              onRemovePending={removePendingMedia}
              imageN={imageN}
              onImageNChange={hasImageTool ? setImageN : undefined}
              videoDuration={videoDuration}
              onVideoDurationChange={hasVideoTool ? setVideoDuration : undefined}
              carryForwardHint={carriedMedia.length > 0 && pendingMedia.length === 0 ? "将沿用上一轮附图（可在智能体配置中关闭）" : undefined}
              disabled={!selectedAgent}
              placeholder={!selectedAgent ? "请先选择智能体" : !conversationId ? "输入消息，发送时自动创建会话" : undefined}
              sendDisabled={chatting || uploadingMedia || !selectedAgent || (!query.trim() && pendingMedia.length === 0 && carriedMedia.length === 0)}
              uploadingMedia={uploadingMedia}
              chatting={chatting}
              sendLabel={generativeToolBusyLabel(pendingTool?.slug) ?? "思考中…"}
            />
          </div>
        </footer>
      </section>

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
        conversationId={conversationId}
        activeTab={workbenchTab}
        rightRailCollapsed={rightCollapsed}
        chatMessages={messages}
        traceTurnIndex={selectedTurnIndex}
        onTraceTurnIndexChange={setSelectedTurnIndex}
        onOpenTrace={openTraceLatest}
        onOpenTraceFromRecord={async (sessionId) => {
          await handleOpenTraceFromRecord(sessionId);
          openTraceLatest();
        }}
        onClose={closePanel}
        onSaved={() => {
          void list.reload();
          closePanel();
        }}
      />
      {confirmDialog}
    </div>
  );
}
