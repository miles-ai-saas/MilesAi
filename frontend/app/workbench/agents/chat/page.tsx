"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AgentChatLeftSidebar } from "@/components/agent/AgentChatLeftSidebar";
import { AgentWorkbenchOverlay } from "@/components/agent/AgentWorkbenchOverlay";
import { AgentWorkbenchSidebar } from "@/components/agent/AgentWorkbenchSidebar";
import { ChatMessageThread } from "@/components/agent/ChatMessageThread";
import {
  loadChatSidebarPrefs,
  saveChatSidebarPrefs,
} from "@/components/agent/chat-sidebar-layout";
import {
  isAgentWorkbenchTab,
  type AgentWorkbenchTab,
} from "@/components/agent/agent-workbench-tabs";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import {
  appendTurn,
  createSession,
  deleteSession,
  ensureActiveSession,
  getSession,
  listSessions,
  setActiveSessionId,
  type ChatMessage,
  type ChatSession,
} from "@/lib/chat-sessions";
import { useInfiniteList } from "@/hooks/use-infinite-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";

export default function AgentsChatPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[calc(100vh-3.5rem)] items-center justify-center text-ink-muted">
          加载对话工作台…
        </div>
      }
    >
      <AgentsChatContent />
    </Suspense>
  );
}

function AgentsChatContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const agentFromUrl = searchParams.get("agent");
  const convFromUrl = searchParams.get("conv");
  const tabFromUrl = searchParams.get("tab");
  const { ready } = useRequireAuth();

  const [selectedAgent, setSelectedAgent] = useState<string>(agentFromUrl ?? "");
  const [conversationId, setConversationId] = useState("");
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionTitle, setSessionTitle] = useState("新对话");

  const [workbenchTab, setWorkbenchTab] = useState<AgentWorkbenchTab>("config");
  const [panelOpen, setPanelOpen] = useState(false);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [query, setQuery] = useState("");
  const [chatting, setChatting] = useState(false);
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const list = useInfiniteList(useCallback((p, s) => api.listAgents(p, s), []), {
    enabled: ready,
    pageSize: 30,
  });

  const refreshSessions = useCallback((agentId: string) => {
    setSessions(listSessions(agentId));
  }, []);

  const loadSessionIntoUi = useCallback(
    (agentId: string, sessionId: string) => {
      const session = getSession(agentId, sessionId);
      if (!session) return;
      setConversationId(session.id);
      setMessages([...session.messages]);
      setSessionTitle(session.title);
      setQuery("");
    },
    [],
  );

  const syncAgentUrl = useCallback(
    (agentId: string, convId?: string) => {
      const params = new URLSearchParams();
      params.set("agent", agentId);
      if (convId) params.set("conv", convId);
      if (isAgentWorkbenchTab(tabFromUrl) && panelOpen) {
        if (workbenchTab !== "config") params.set("tab", workbenchTab);
      }
      router.replace(`/workbench/agents/chat?${params.toString()}`);
    },
    [router, tabFromUrl, panelOpen, workbenchTab],
  );

  useEffect(() => {
    const prefs = loadChatSidebarPrefs();
    if (prefs.leftCollapsed) setLeftCollapsed(true);
    if (prefs.rightCollapsed) setRightCollapsed(true);
  }, []);

  useEffect(() => {
    if (isAgentWorkbenchTab(tabFromUrl)) {
      setWorkbenchTab(tabFromUrl);
      setPanelOpen(true);
    }
  }, [tabFromUrl]);

  useEffect(() => {
    if (!selectedAgent && list.items[0]) {
      setSelectedAgent(list.items[0].id);
    }
  }, [list.items, selectedAgent]);

  useEffect(() => {
    if (agentFromUrl) setSelectedAgent(agentFromUrl);
  }, [agentFromUrl]);

  useEffect(() => {
    if (!selectedAgent) return;
    refreshSessions(selectedAgent);

    let session: ChatSession | null = null;
    if (convFromUrl) {
      session = getSession(selectedAgent, convFromUrl);
      if (session) setActiveSessionId(selectedAgent, convFromUrl);
    }
    if (!session) {
      session = ensureActiveSession(selectedAgent);
    }
    loadSessionIntoUi(selectedAgent, session.id);
    syncAgentUrl(selectedAgent, session.id);
  }, [selectedAgent, convFromUrl, refreshSessions, loadSessionIntoUi, syncAgentUrl]);

  const selected = list.items.find((a) => a.id === selectedAgent);

  const persistSidebar = (patch: { left?: boolean; right?: boolean }) => {
    saveChatSidebarPrefs({
      leftCollapsed: patch.left ?? leftCollapsed,
      rightCollapsed: patch.right ?? rightCollapsed,
    });
  };

  const handleNewSession = () => {
    if (!selectedAgent) return;
    const session = createSession(selectedAgent);
    refreshSessions(selectedAgent);
    loadSessionIntoUi(selectedAgent, session.id);
    syncAgentUrl(selectedAgent, session.id);
  };

  const handleSelectSession = (sessionId: string) => {
    if (!selectedAgent) return;
    setActiveSessionId(selectedAgent, sessionId);
    loadSessionIntoUi(selectedAgent, sessionId);
    syncAgentUrl(selectedAgent, sessionId);
    setPanelOpen(false);
  };

  const handleDeleteSession = (sessionId: string) => {
    if (!selectedAgent) return;
    requestConfirm({
      title: "删除会话",
      description: "此操作不可撤销。",
      message: "确定删除该会话？本地消息记录将无法恢复。",
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: () => {
        deleteSession(selectedAgent, sessionId);
        refreshSessions(selectedAgent);
        const next = ensureActiveSession(selectedAgent);
        loadSessionIntoUi(selectedAgent, next.id);
        syncAgentUrl(selectedAgent, next.id);
      },
    });
  };

  const onSelectAgent = (id: string) => {
    setSelectedAgent(id);
    setPanelOpen(false);
    const params = new URLSearchParams();
    params.set("agent", id);
    router.replace(`/workbench/agents/chat?${params.toString()}`);
  };

  const onTabChange = (tab: AgentWorkbenchTab) => {
    setWorkbenchTab(tab);
    setPanelOpen(true);
    const params = new URLSearchParams();
    if (selectedAgent) params.set("agent", selectedAgent);
    if (conversationId) params.set("conv", conversationId);
    if (tab !== "config") params.set("tab", tab);
    router.replace(`/workbench/agents/chat?${params.toString()}`);
  };

  const closePanel = () => {
    setPanelOpen(false);
    const params = new URLSearchParams();
    if (selectedAgent) params.set("agent", selectedAgent);
    if (conversationId) params.set("conv", conversationId);
    router.replace(`/workbench/agents/chat?${params.toString()}`);
  };

  const chat = async () => {
    if (!selectedAgent || !conversationId || !query.trim()) return;
    const userText = query.trim();
    setChatting(true);
    setQuery("");
    const optimistic: ChatMessage[] = [
      ...messages,
      { role: "user", content: userText },
    ];
    setMessages(optimistic);

    try {
      const res = await api.chatAgent(selectedAgent, userText, { conversationId });
      const nextMessages: ChatMessage[] = [
        ...optimistic,
        {
          role: "assistant",
          content: res.answer,
          steps: res.steps?.length ? res.steps : undefined,
        },
      ];
      setMessages(nextMessages);
      appendTurn(selectedAgent, conversationId, userText, res.answer, res.steps ?? []);
      refreshSessions(selectedAgent);
      const updated = getSession(selectedAgent, conversationId);
      if (updated) setSessionTitle(updated.title);
    } catch (e) {
      const err = e instanceof Error ? e.message : "对话失败";
      setMessages([
        ...optimistic,
        { role: "assistant", content: err },
      ]);
    } finally {
      setChatting(false);
    }
  };

  if (!ready || list.loading) {
    return (
      <div className="flex h-[calc(100vh-3.5rem)] items-center justify-center text-ink-muted">
        加载对话工作台…
      </div>
    );
  }

  return (
    <div className="relative flex h-[calc(100vh-3.5rem)]">
      <AgentChatLeftSidebar
        agents={list.items}
        total={list.total}
        selectedAgentId={selectedAgent}
        sessions={sessions}
        activeSessionId={conversationId || null}
        collapsed={leftCollapsed}
        hasMoreAgents={list.hasMore}
        loadingMoreAgents={list.loadingMore}
        onLoadMoreAgents={() => void list.loadMore()}
        onToggleCollapse={() => {
          const next = !leftCollapsed;
          setLeftCollapsed(next);
          persistSidebar({ left: next });
        }}
        onSelectAgent={onSelectAgent}
        onNewSession={handleNewSession}
        onSelectSession={handleSelectSession}
        onDeleteSession={handleDeleteSession}
      />

      <section className="flex min-w-0 flex-1 flex-col bg-surface-subtle">
        <div className="flex items-start justify-between gap-4 border-b border-line bg-surface px-6 py-3">
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-lg font-semibold text-ink">
              {selected?.name ?? "选择智能体"}
            </h2>
            <p className="mt-0.5 truncate text-sm text-ink-muted" title={sessionTitle}>
              {sessionTitle}
            </p>
          </div>
          <button type="button" className="btn-sm-outline shrink-0" onClick={handleNewSession}>
            新会话
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          <ChatMessageThread messages={messages} chatting={chatting} />
        </div>

        <div className="border-t border-line bg-surface p-4">
          <div className="mx-auto flex max-w-3xl gap-2">
            <textarea
              className="input-field min-h-[44px] flex-1 resize-none py-2.5"
              rows={2}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void chat();
                }
              }}
              placeholder="输入问题，Enter 发送，Shift+Enter 换行"
              disabled={!selectedAgent || !conversationId}
            />
            <button
              type="button"
              onClick={() => void chat()}
              disabled={chatting || !selectedAgent || !conversationId}
              className="btn-primary shrink-0 self-end px-5 py-2 text-sm"
            >
              {chatting ? "思考中…" : "发送"}
            </button>
          </div>
        </div>
      </section>

      <div className="hidden h-full shrink-0 lg:block">
        <AgentWorkbenchSidebar
          agent={selected ?? null}
          activeTab={workbenchTab}
          panelOpen={panelOpen}
          collapsed={rightCollapsed}
          onToggleCollapse={() => {
            const next = !rightCollapsed;
            setRightCollapsed(next);
            persistSidebar({ right: next });
          }}
          onTabChange={onTabChange}
        />
      </div>

      <AgentWorkbenchOverlay
        open={panelOpen}
        agent={selected ?? null}
        agentId={selectedAgent || null}
        activeTab={workbenchTab}
        rightRailCollapsed={rightCollapsed}
        onClose={closePanel}
        onSaved={() => list.reload()}
      />
      {confirmDialog}
    </div>
  );
}
