"use client";

import { AgentChatDebugHeader } from "@/features/agents/components/AgentChatDebugHeader";
import { AgentChatComposer } from "@/features/agents/components/AgentChatComposer";
import { ChatMessageThread } from "@/features/agents/components/ChatMessageThread";
import type { AgentsChatPageVm } from "@/features/agents/hooks/use-agents-chat-page";
import { generativeToolBusyLabel } from "@/lib/generative-tool-ui";

type Props = Pick<
  AgentsChatPageVm,
  | "sessionTitle"
  | "selectedAgent"
  | "conversationId"
  | "messages"
  | "selected"
  | "wsEnabled"
  | "wsReady"
  | "lastTraceId"
  | "focusMode"
  | "agentsColumnCompact"
  | "query"
  | "setQuery"
  | "pendingMedia"
  | "uploadingMedia"
  | "chatting"
  | "pendingTool"
  | "carriedMedia"
  | "chattingStatusLabel"
  | "generativeStatusEl"
  | "handleNewSession"
  | "handleRenameSession"
  | "openTraceLatest"
  | "openTraceAtTurn"
  | "chat"
  | "confirmPendingTool"
  | "onPickAttachments"
  | "removePendingMedia"
  | "handleAgentRenamed"
  | "setLeftDrawerOpen"
  | "setFocusMode"
  | "setAgentsColumnCompact"
  | "persistSidebar"
>;

export function AgentsChatMainColumn({
  sessionTitle,
  selectedAgent,
  conversationId,
  messages,
  selected,
  wsEnabled,
  wsReady,
  lastTraceId,
  focusMode,
  agentsColumnCompact,
  query,
  setQuery,
  pendingMedia,
  uploadingMedia,
  chatting,
  pendingTool,
  carriedMedia,
  chattingStatusLabel,
  generativeStatusEl,
  handleNewSession,
  handleRenameSession,
  openTraceLatest,
  openTraceAtTurn,
  chat,
  confirmPendingTool,
  onPickAttachments,
  removePendingMedia,
  handleAgentRenamed,
  setLeftDrawerOpen,
  setFocusMode,
  setAgentsColumnCompact,
  persistSidebar,
}: Props) {
  return (
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

      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-4 sm:px-4">
        <div className="mx-auto w-full max-w-4xl">
          <ChatMessageThread
            messages={messages}
            chatting={chatting}
            chattingStatusLabel={chattingStatusLabel}
            pendingTool={pendingTool}
            onConfirmPendingTool={() => void confirmPendingTool()}
            confirmPendingToolDisabled={chatting}
            generativeStatus={generativeStatusEl}
            onOpenTraceTurn={openTraceAtTurn}
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
            carryForwardHint={carriedMedia.length > 0 && pendingMedia.length === 0 ? "将沿用上一轮附图（可在智能体配置中关闭）" : undefined}
            disabled={!selectedAgent || !conversationId}
            sendDisabled={
              chatting || uploadingMedia || !selectedAgent || !conversationId || (!query.trim() && pendingMedia.length === 0 && carriedMedia.length === 0)
            }
            uploadingMedia={uploadingMedia}
            chatting={chatting}
            sendLabel={generativeToolBusyLabel(pendingTool?.slug) ?? "思考中…"}
          />
        </div>
      </footer>
    </section>
  );
}
