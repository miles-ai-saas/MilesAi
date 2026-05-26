"use client";

/**
 * 智能体对话工作台（链路 §5，见 `lib/chains.ts`）。
 * 会话：`chat-sessions`；发送：`api.chatAgent`；Trace：`agent-trace` / `agent-steps`。
 */

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AgentChatLeftSidebar } from "@/components/agent/AgentChatLeftSidebar";
import { AgentWorkbenchOverlay } from "@/components/agent/AgentWorkbenchOverlay";
import { AgentWorkbenchSidebar } from "@/components/agent/AgentWorkbenchSidebar";
import { useTraceTurnSelection } from "@/components/agent/AgentTracePanel";
import { ChatMessageThread } from "@/components/agent/ChatMessageThread";
import {
  loadChatSidebarPrefs,
  saveChatSidebarPrefs,
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
  agentCarryForwardMediaEnabled,
  lastUserMessageMedia,
  resolveOutgoingChatMedia,
} from "@/lib/chat-media-forward";
import type { ChatAgentResult, ChatArtifact, ChatMediaIn, GenerativeJobOut } from "@/lib/types";

type PendingMedia = ChatMessageMedia & { local_preview: string };
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
  const [query, setQuery] = useState("");
  const [pendingMedia, setPendingMedia] = useState<PendingMedia[]>([]);
  const [uploadingMedia, setUploadingMedia] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
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

  const onPickImages = async (files: FileList | null) => {
    if (!files?.length || uploadingMedia) return;
    setUploadingMedia(true);
    try {
      const next: PendingMedia[] = [];
      for (const file of Array.from(files)) {
        if (!file.type.startsWith("image/")) continue;
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
        setPendingMedia((prev) => [...prev, ...next].slice(0, 4));
      }
    } catch (e) {
      const err = e instanceof Error ? e.message : "图片上传失败";
      window.alert(err);
    } finally {
      setUploadingMedia(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
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
    <div className="relative flex h-[calc(100vh-3.5rem)]">
      <AgentChatLeftSidebar
        agents={list.items}
        total={list.total}
        selectedAgentId={selectedAgent}
        sessions={sessions}
        activeSessionId={conversationId || null}
        collapsed={leftCollapsed}
        hideCollapseButton={panelOpen}
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
          <ChatMessageThread
            messages={messages}
            chatting={chatting}
            chattingStatusLabel={chattingStatusLabel}
            pendingTool={pendingTool}
            onConfirmPendingTool={() => void confirmPendingTool()}
            confirmPendingToolDisabled={chatting}
          />
        </div>

        <div className="border-t border-line bg-surface p-4">
          <div className="mx-auto max-w-3xl space-y-2">
            {(generativePollMsg || wsGenerativeMsg) ? (
              <div className="rounded-lg border border-amber-200/80 bg-amber-50/90 px-3 py-2 text-xs text-amber-900">
                <div className="flex items-center justify-between gap-2">
                  <span>{wsGenerativeMsg ?? generativePollMsg}</span>
                  {(canCancelGenerative || wsActiveJobIds.length > 0) ? (
                    <button
                      type="button"
                      className="btn-sm-ghost shrink-0 text-xs text-amber-900"
                      onClick={() => {
                        if (wsActiveJobIds.length && wsClientRef.current?.connected) {
                          for (const id of wsActiveJobIds) {
                            wsClientRef.current.cancelGenerativeJob(id);
                          }
                          setWsGenerativeMsg("已请求取消…");
                        } else {
                          for (const j of pollJobs) void cancelGenerativeJob(j.jobId);
                        }
                      }}
                    >
                      取消
                    </button>
                  ) : null}
                </div>
                {(generativeProgress ?? wsGenerativeProgress) != null ? (
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-amber-200/60">
                    <div
                      className="h-full rounded-full bg-amber-600 transition-all duration-300"
                      style={{ width: `${generativeProgress ?? wsGenerativeProgress}%` }}
                    />
                  </div>
                ) : null}
              </div>
            ) : null}
            {(pendingMedia.length > 0 || carriedMedia.length > 0) && (
              <div className="space-y-1">
                {carriedMedia.length > 0 && pendingMedia.length === 0 && (
                  <p className="text-[11px] text-ink-muted">将沿用上一轮附图（可在智能体配置中关闭）</p>
                )}
                <div className="flex flex-wrap gap-2">
                  {pendingMedia.map((m) => (
                    <div key={m.attachment_id} className="relative">
                      <img
                        src={m.local_preview}
                        alt={m.filename ?? "待发送"}
                        className="h-16 w-16 rounded-lg object-cover ring-1 ring-line"
                      />
                      <button
                        type="button"
                        className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-ink text-xs text-surface"
                        aria-label="移除图片"
                        onClick={() => removePendingMedia(m.attachment_id)}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                  {carriedMedia.map((m) => (
                    <div
                      key={`carry-${m.attachment_id}`}
                      className="h-16 w-16 overflow-hidden rounded-lg ring-1 ring-dashed ring-brand/40"
                      title={m.filename ?? "上一轮附图"}
                    >
                      {m.preview_url ? (
                        <img
                          src={m.preview_url}
                          alt={m.filename ?? "上一轮附图"}
                          className="h-full w-full object-cover opacity-90"
                        />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center bg-surface-muted text-[10px] text-ink-faint">
                          附图
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="flex gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                multiple
                className="hidden"
                onChange={(e) => void onPickImages(e.target.files)}
              />
              <button
                type="button"
                className="btn-sm-outline shrink-0 self-end"
                disabled={!selectedAgent || !conversationId || uploadingMedia || chatting}
                onClick={() => fileInputRef.current?.click()}
                title="上传图片（最多 4 张）"
              >
                {uploadingMedia ? "上传中…" : "图片"}
              </button>
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
                placeholder="输入问题或附图，Enter 发送"
                disabled={!selectedAgent || !conversationId}
              />
              <button
                type="button"
                onClick={() => void chat()}
                disabled={
                  chatting ||
                  uploadingMedia ||
                  !selectedAgent ||
                  !conversationId ||
                  (!query.trim() && pendingMedia.length === 0 && carriedMedia.length === 0)
                }
                className="btn-primary shrink-0 self-end px-5 py-2 text-sm"
              >
                {chatting
                  ? (generativeToolBusyLabel(pendingTool?.slug) ?? "思考中…")
                  : "发送"}
              </button>
            </div>
          </div>
        </div>
      </section>

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
