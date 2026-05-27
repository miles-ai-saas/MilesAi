"use client";

/**
 * 智能体对话工作台（链路 §5，见 `lib/chains.ts`）。
 * 会话：`chat-sessions`；发送：`api.chatAgent`；Trace：`agent-trace` / `agent-steps`。
 */

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AgentChatDebugHeader } from "@/components/agent/AgentChatDebugHeader";
import { AgentChatLeftSidebar } from "@/components/agent/AgentChatLeftSidebar";
import { AgentWorkbenchOverlay } from "@/components/agent/AgentWorkbenchOverlay";
import { AgentWorkbenchSidebar } from "@/components/agent/AgentWorkbenchSidebar";
import { ChatGenerativeStatusBanner } from "@/components/agent/ChatGenerativeStatusBanner";
import { useTraceTurnSelection } from "@/components/agent/AgentTracePanel";
import { defaultTraceTurnIndex, listTraceTurns } from "@/lib/agent-trace";
import {
  AgentChatComposer,
  type PendingChatMedia,
} from "@/components/agent/AgentChatComposer";
import { ChatMessageThread } from "@/components/agent/ChatMessageThread";
import {
  loadChatSidebarPrefs,
  saveChatSidebarPrefs,
  type ChatSidebarPrefs,
} from "@/components/agent/chat-sidebar-layout";
import {
  normalizeAgentWorkbenchTab,
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
  renameSession,
  setActiveSessionId,
  type ChatMessage,
  type ChatMessageMedia,
  type ChatSession,
} from "@/lib/chat-sessions";
import { useAgentChatWs } from "@/hooks/use-agent-chat-ws";
import { useGenerativeJobPoll } from "@/hooks/use-generative-job-poll";
import {
  extractPendingGenerativeJobs,
  generativeJobToArtifacts,
} from "@/lib/generative-jobs";
import { generativeToolBusyLabel } from "@/lib/generative-tool-ui";
import {
  CHAT_ATTACHMENT_MAX_COUNT,
  filterChatUploadFiles,
} from "@/lib/chat-attachments";
import {
  agentCarryForwardMediaEnabled,
  lastUserMessageMedia,
  resolveOutgoingChatMedia,
} from "@/lib/chat-media-forward";
import type { ChatAgentResult, ChatArtifact, ChatMediaIn, GenerativeJobOut } from "@/lib/types";
import { useInfiniteList } from "@/hooks/use-infinite-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import type { PendingToolCall } from "@/lib/types";

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
  const [agentsColumnCompact, setAgentsColumnCompact] = useState(true);
  const [focusMode, setFocusMode] = useState(false);
  const [leftDrawerOpen, setLeftDrawerOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [pendingMedia, setPendingMedia] = useState<PendingChatMedia[]>([]);
  const [uploadingMedia, setUploadingMedia] = useState(false);
  const [chatting, setChatting] = useState(false);
  const [pendingTool, setPendingTool] = useState<PendingToolCall | null>(null);
  const [pollJobs, setPollJobs] = useState<{ jobId: string; kind: string }[]>([]);
  const [wsGenerativeMsg, setWsGenerativeMsg] = useState<string | null>(null);
  const [wsGenerativeProgress, setWsGenerativeProgress] = useState<number | null>(null);
  const [wsActiveJobIds, setWsActiveJobIds] = useState<string[]>([]);

  const { wsEnabled, wsReady, client: wsClientRef } = useAgentChatWs(
    selectedAgent,
    conversationId,
  );

  const {
    statusMsg: generativePollMsg,
    progressPercent: generativeProgress,
    cancelJob: cancelGenerativeJob,
    canCancel: canCancelGenerative,
  } = useGenerativeJobPoll(pollJobs, (artifacts) => {
    setMessages((prev) => {
      if (!prev.length) return prev;
      const lastIdx = prev.length - 1;
      if (prev[lastIdx].role !== "assistant") return prev;
      const merged = [...(prev[lastIdx].artifacts ?? [])];
      for (const a of artifacts) {
        if (!merged.some((m) => m.attachment_id === a.attachment_id)) {
          merged.push({
            kind: a.kind,
            attachment_id: a.attachment_id,
            mime_type: a.mime_type ?? undefined,
          });
        }
      }
      const next = [...prev];
      next[lastIdx] = { ...prev[lastIdx], artifacts: merged };
      return next;
    });
    setPollJobs([]);
  });
  const { selectedTurnIndex, setSelectedTurnIndex } = useTraceTurnSelection(messages, conversationId);
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
      setPendingMedia([]);
    },
    [],
  );

  const syncAgentUrl = useCallback(
    (agentId: string, convId?: string) => {
      const params = new URLSearchParams();
      params.set("agent", agentId);
      if (convId) params.set("conv", convId);
      if (normalizeAgentWorkbenchTab(tabFromUrl) && panelOpen) {
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
    if (prefs.agentsColumnCompact === false) setAgentsColumnCompact(false);
    if (prefs.focusMode) setFocusMode(true);
  }, []);

  useEffect(() => {
    const tab = normalizeAgentWorkbenchTab(tabFromUrl);
    if (tab) {
      setWorkbenchTab(tab);
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
  const carryForwardMedia = agentCarryForwardMediaEnabled(
    (selected?.config ?? null) as Record<string, unknown> | null,
  );
  const carriedMedia = useMemo(() => {
    if (pendingMedia.length > 0 || !carryForwardMedia) return [];
    return lastUserMessageMedia(messages);
  }, [pendingMedia.length, carryForwardMedia, messages]);

  const persistSidebar = (patch: Partial<ChatSidebarPrefs>) => {
    saveChatSidebarPrefs({
      leftCollapsed: patch.leftCollapsed ?? leftCollapsed,
      rightCollapsed: patch.rightCollapsed ?? rightCollapsed,
      agentsColumnCompact: patch.agentsColumnCompact ?? agentsColumnCompact,
      focusMode: patch.focusMode ?? focusMode,
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
    setLeftDrawerOpen(false);
  };

  const handleRenameSession = useCallback(
    (sessionId: string, title: string) => {
      if (!selectedAgent) return;
      if (!renameSession(selectedAgent, sessionId, title)) return;
      refreshSessions(selectedAgent);
      if (sessionId === conversationId) {
        const updated = getSession(selectedAgent, sessionId);
        if (updated) setSessionTitle(updated.title);
      }
    },
    [conversationId, refreshSessions, selectedAgent],
  );

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

  const onTabChange = useCallback(
    (tab: AgentWorkbenchTab) => {
      setWorkbenchTab(tab);
      setPanelOpen(true);
      const params = new URLSearchParams();
      if (selectedAgent) params.set("agent", selectedAgent);
      if (conversationId) params.set("conv", conversationId);
      if (tab !== "config") params.set("tab", tab);
      router.replace(`/workbench/agents/chat?${params.toString()}`);
    },
    [conversationId, router, selectedAgent],
  );

  const openTraceAtTurn = useCallback(
    (turnIndex: number) => {
      setSelectedTurnIndex(turnIndex);
      onTabChange("trace");
    },
    [onTabChange, setSelectedTurnIndex],
  );

  const openTraceLatest = useCallback(() => {
    const turns = listTraceTurns(messages);
    setSelectedTurnIndex(defaultTraceTurnIndex(turns));
    onTabChange("trace");
  }, [messages, onTabChange, setSelectedTurnIndex]);

  const closePanel = () => {
    setPanelOpen(false);
    const params = new URLSearchParams();
    if (selectedAgent) params.set("agent", selectedAgent);
    if (conversationId) params.set("conv", conversationId);
    router.replace(`/workbench/agents/chat?${params.toString()}`);
  };

  const onPickAttachments = async (files: FileList | null) => {
    if (!files?.length || uploadingMedia) return;
    const picked = filterChatUploadFiles(files);
    if (!picked.length) {
      window.alert("当前仅支持上传图片（JPEG / PNG / WebP / GIF）");
      return;
    }
    setUploadingMedia(true);
    try {
      const next: PendingChatMedia[] = [];
      for (const file of picked) {
        const att = await api.uploadAttachment(file, { purpose: "chat" });
        const local_preview = URL.createObjectURL(file);
        next.push({
          attachment_id: att.id,
          filename: att.filename,
          preview_url: local_preview,
          local_preview,
        });
      }
      if (next.length) {
        setPendingMedia((prev) => [...prev, ...next].slice(0, CHAT_ATTACHMENT_MAX_COUNT));
      }
    } catch (e) {
      const err = e instanceof Error ? e.message : "附件上传失败";
      window.alert(err);
    } finally {
      setUploadingMedia(false);
    }
  };

  const removePendingMedia = (attachmentId: string) => {
    setPendingMedia((prev) => {
      const item = prev.find((p) => p.attachment_id === attachmentId);
      if (item?.local_preview) URL.revokeObjectURL(item.local_preview);
      return prev.filter((p) => p.attachment_id !== attachmentId);
    });
  };

  const mergeGenerativeArtifacts = useCallback((artifacts: ChatArtifact[]) => {
    if (!artifacts.length) return;
    setMessages((prev) => {
      if (!prev.length) return prev;
      const lastIdx = prev.length - 1;
      if (prev[lastIdx].role !== "assistant") return prev;
      const merged = [...(prev[lastIdx].artifacts ?? [])];
      for (const a of artifacts) {
        if (!merged.some((m) => m.attachment_id === a.attachment_id)) {
          merged.push({
            kind: a.kind,
            attachment_id: a.attachment_id,
            mime_type: a.mime_type ?? undefined,
          });
        }
      }
      const next = [...prev];
      next[lastIdx] = { ...prev[lastIdx], artifacts: merged };
      return next;
    });
  }, []);

  const handleWsGenerativeJob = useCallback(
    (job: GenerativeJobOut, phase: "queued" | "progress" | "done") => {
      setWsActiveJobIds((prev) =>
        prev.includes(job.id) ? prev : [...prev, job.id],
      );
      if (job.progress_percent != null) setWsGenerativeProgress(job.progress_percent);
      const label = job.progress_message || "生成中…";
      setWsGenerativeMsg(
        job.progress_percent != null ? `${label}（${job.progress_percent}%）` : label,
      );
      if (phase === "done") {
        setWsActiveJobIds((prev) => prev.filter((id) => id !== job.id));
        if (job.status === "success") {
          mergeGenerativeArtifacts(generativeJobToArtifacts(job));
          setWsGenerativeMsg(null);
          setWsGenerativeProgress(null);
        } else if (job.status === "failed") {
          setWsGenerativeMsg(job.error_message ?? "生成失败");
        } else if (job.status === "cancelled") {
          setWsGenerativeMsg("任务已取消");
        }
      }
    },
    [mergeGenerativeArtifacts],
  );

  const applyChatResponse = useCallback(
    (
      res: ChatAgentResult,
      optimistic: ChatMessage[],
      userText: string,
      userMedia: ChatMessageMedia[],
      useWsJobs: boolean,
    ) => {
      setPendingTool(res.pending_tool ?? null);
      if (!useWsJobs) {
        const pendingJobs = [
          ...extractPendingGenerativeJobs(res.steps).map((j) => ({
            jobId: j.jobId,
            kind: j.kind,
          })),
          ...(res.generative_jobs ?? [])
            .filter((j) => j.status === "pending")
            .map((j) => ({ jobId: j.id, kind: j.kind })),
        ];
        setPollJobs(pendingJobs);
      } else {
        setPollJobs([]);
        const pendingIds = [
          ...extractPendingGenerativeJobs(res.steps).map((j) => j.jobId),
          ...(res.generative_jobs ?? [])
            .filter((j) => j.status === "pending")
            .map((j) => j.id),
        ];
        setWsActiveJobIds(pendingIds);
        if (pendingIds.length) {
          setWsGenerativeMsg(`正在生成（${pendingIds.length} 个任务）…`);
        }
      }
      const nextMessages: ChatMessage[] = [
        ...optimistic,
        {
          role: "assistant",
          content: res.answer,
          artifacts: res.artifacts?.map((a) => ({
            kind: a.kind,
            attachment_id: a.attachment_id,
            mime_type: a.mime_type,
          })),
          steps: res.steps?.length ? res.steps : undefined,
          traceId: res.trace_id,
        },
      ];
      setMessages(nextMessages);
      appendTurn(
        selectedAgent,
        conversationId,
        userText,
        res.answer,
        res.steps ?? [],
        res.trace_id,
        userMedia.length ? userMedia : undefined,
      );
      refreshSessions(selectedAgent);
      const updated = getSession(selectedAgent, conversationId);
      if (updated) setSessionTitle(updated.title);
    },
    [conversationId, refreshSessions, selectedAgent],
  );

  const chat = async () => {
    if (!selectedAgent || !conversationId) return;
    const userText = query.trim();
    const pendingPayload: ChatMediaIn[] = pendingMedia.map((m) => ({
      attachment_id: m.attachment_id,
    }));
    const { payload: mediaPayload, carriedFromPrevious } = resolveOutgoingChatMedia(
      pendingPayload,
      messages,
      carryForwardMedia,
    );
    if (!userText && mediaPayload.length === 0) return;

    const userMedia: ChatMessageMedia[] = pendingMedia.length
      ? pendingMedia.map((m) => ({
          attachment_id: m.attachment_id,
          filename: m.filename,
          preview_url: m.preview_url,
        }))
      : carriedFromPrevious
        ? carriedMedia.map((m) => ({
            attachment_id: m.attachment_id,
            filename: m.filename,
            preview_url: m.preview_url,
          }))
        : [];

    setChatting(true);
    setQuery("");
    setPendingMedia([]);
    const optimistic: ChatMessage[] = [
      ...messages,
      {
        role: "user",
        content: userText,
        ...(userMedia.length ? { media: userMedia } : {}),
      },
    ];
    setMessages(optimistic);

    const useWs = wsEnabled && wsReady && wsClientRef.current?.connected;

    try {
      if (useWs && wsClientRef.current) {
        let streamText = "";
        setMessages([...optimistic, { role: "assistant", content: "" }]);
        const res = await wsClientRef.current.sendChat(
          {
            query: userText,
            media: mediaPayload.length ? mediaPayload : undefined,
          },
          {
            onDelta: (chunk) => {
              streamText += chunk;
              setMessages([...optimistic, { role: "assistant", content: streamText }]);
            },
            onToolConfirmRequired: (tool) =>
              setPendingTool({
                slug: tool.slug,
                name: tool.name,
                description: tool.description ?? undefined,
                params: tool.params,
              }),
            onGenerativeJob: handleWsGenerativeJob,
          },
        );
        applyChatResponse(res, optimistic, userText, userMedia, true);
      } else {
        const res = await api.chatAgent(selectedAgent, userText, {
          conversationId,
          media: mediaPayload.length ? mediaPayload : undefined,
        });
        applyChatResponse(res, optimistic, userText, userMedia, false);
      }
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

  const chattingStatusLabel =
    chatting && pendingTool
      ? generativeToolBusyLabel(pendingTool.slug) ?? "思考中…"
      : chatting
        ? "思考中…"
        : null;

  const lastTraceId = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const m = messages[i];
      if (m.role === "assistant" && m.traceId) return m.traceId;
    }
    return null;
  }, [messages]);

  const generativeStatusMessage = wsGenerativeMsg ?? generativePollMsg;
  const generativeProgressValue = generativeProgress ?? wsGenerativeProgress;

  const handleCancelGenerative = useCallback(() => {
    if (wsActiveJobIds.length && wsClientRef.current?.connected) {
      for (const id of wsActiveJobIds) {
        wsClientRef.current.cancelGenerativeJob(id);
      }
      setWsGenerativeMsg("已请求取消…");
    } else {
      for (const j of pollJobs) void cancelGenerativeJob(j.jobId);
    }
  }, [cancelGenerativeJob, pollJobs, wsActiveJobIds, wsClientRef]);

  const handleAgentRenamed = useCallback(() => {
    void list.reload();
  }, [list]);

  const generativeStatusEl =
    generativeStatusMessage ? (
      <ChatGenerativeStatusBanner
        message={generativeStatusMessage}
        progressPercent={generativeProgressValue}
        canCancel={canCancelGenerative || wsActiveJobIds.length > 0}
        onCancel={handleCancelGenerative}
      />
    ) : null;

  const leftSidebarProps = {
    agents: list.items,
    total: list.total,
    selectedAgentId: selectedAgent,
    sessions,
    activeSessionId: conversationId || null,
    collapsed: leftCollapsed,
    agentsColumnCompact,
    hasMoreAgents: list.hasMore,
    loadingMoreAgents: list.loadingMore,
    onLoadMoreAgents: () => void list.loadMore(),
    onSelectAgent: onSelectAgent,
    onNewSession: handleNewSession,
    onSelectSession: handleSelectSession,
    onRenameSession: handleRenameSession,
    onDeleteSession: handleDeleteSession,
  };

  const confirmPendingTool = async () => {
    if (!selectedAgent || !conversationId || !pendingTool) return;
    setChatting(true);
    const useWs = wsEnabled && wsReady && wsClientRef.current?.connected;
    try {
      let res: ChatAgentResult;
      if (useWs && wsClientRef.current) {
        let streamText = "";
        const base = messages;
        setMessages([...base, { role: "assistant", content: "" }]);
        res = await wsClientRef.current.sendChat(
          {
            query: "确认执行工具",
            toolConfirmed: true,
            pendingToolSlug: pendingTool.slug,
            pendingToolParams: pendingTool.params,
          },
          {
            onDelta: (chunk) => {
              streamText += chunk;
              setMessages([...base, { role: "assistant", content: streamText }]);
            },
            onToolConfirmRequired: (tool) =>
              setPendingTool({
                slug: tool.slug,
                name: tool.name,
                description: tool.description ?? undefined,
                params: tool.params,
              }),
            onGenerativeJob: handleWsGenerativeJob,
          },
        );
      } else {
        res = await api.chatAgent(selectedAgent, "确认执行工具", {
          conversationId,
          toolConfirmed: true,
          pendingToolSlug: pendingTool.slug,
          pendingToolParams: pendingTool.params,
        });
      }
      setPendingTool(res.pending_tool ?? null);
      if (!useWs) {
        const pendingJobs = [
          ...extractPendingGenerativeJobs(res.steps).map((j) => ({
            jobId: j.jobId,
            kind: j.kind,
          })),
          ...(res.generative_jobs ?? [])
            .filter((j) => j.status === "pending")
            .map((j) => ({ jobId: j.id, kind: j.kind })),
        ];
        setPollJobs(pendingJobs);
      } else {
        setPollJobs([]);
      }
      setMessages((prev) => {
        const withoutEmptyTail =
          prev.length &&
          prev[prev.length - 1].role === "assistant" &&
          !prev[prev.length - 1].content
            ? prev.slice(0, -1)
            : prev;
        return [
          ...withoutEmptyTail,
          {
            role: "assistant",
            content: res.answer,
            artifacts: res.artifacts?.map((a) => ({
              kind: a.kind,
              attachment_id: a.attachment_id,
              mime_type: a.mime_type,
            })),
            steps: res.steps?.length ? res.steps : undefined,
            traceId: res.trace_id,
          },
        ];
      });
    } catch (e) {
      const err = e instanceof Error ? e.message : "工具确认失败";
      setMessages((prev) => [...prev, { role: "assistant", content: err }]);
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
          <button
            type="button"
            className="fixed inset-0 z-40 bg-black/30 lg:hidden"
            aria-label="关闭侧栏"
            onClick={() => setLeftDrawerOpen(false)}
          />
          <div className="fixed inset-y-0 left-0 z-50 h-full shadow-xl lg:hidden">
            <AgentChatLeftSidebar
              {...leftSidebarProps}
              hideCollapseButton
              onToggleCollapse={() => setLeftDrawerOpen(false)}
            />
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
              carryForwardHint={
                carriedMedia.length > 0 && pendingMedia.length === 0
                  ? "将沿用上一轮附图（可在智能体配置中关闭）"
                  : undefined
              }
              disabled={!selectedAgent || !conversationId}
              sendDisabled={
                chatting ||
                uploadingMedia ||
                !selectedAgent ||
                !conversationId ||
                (!query.trim() && pendingMedia.length === 0 && carriedMedia.length === 0)
              }
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
          <button
            type="button"
            className="btn-sm-outline pointer-events-auto shadow-md"
            onClick={openTraceLatest}
          >
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
