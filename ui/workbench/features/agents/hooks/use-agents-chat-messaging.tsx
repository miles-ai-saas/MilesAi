"use client";

import { useCallback, useMemo, useState, type Dispatch, type SetStateAction } from "react";
import { ChatGenerativeStatusBanner } from "@/components/agent/ChatGenerativeStatusBanner";
import type { PendingChatMedia } from "@/components/agent/AgentChatComposer";
import { api } from "@/lib/api";
import {
  appendTurn,
  getSession,
  type ChatMessage,
  type ChatMessageMedia,
} from "@/lib/chat-sessions";
import { useAgentChatWs } from "@/hooks/use-agent-chat-ws";
import { useGenerativeJobPoll } from "@/hooks/use-generative-job-poll";
import { generativeJobToArtifacts } from "@/lib/generative-jobs";
import { generativeToolBusyLabel } from "@/lib/generative-tool-ui";
import { CHAT_ATTACHMENT_MAX_COUNT, filterChatUploadFiles } from "@/lib/chat-attachments";
import { resolveOutgoingChatMedia, lastUserMessageMedia } from "@/lib/chat-media-forward";
import {
  collectPendingGenerativeJobIds,
  collectPendingGenerativeJobs,
  mapResponseArtifacts,
  mergeArtifactsIntoLastAssistant,
  type GenerativePollJob,
} from "@/lib/agents-chat-helpers";
import type { ChatAgentResult, ChatMediaIn, GenerativeJobOut, PendingToolCall } from "@/lib/types";

type Params = {
  selectedAgent: string;
  conversationId: string;
  messages: ChatMessage[];
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>;
  setSessionTitle: (title: string) => void;
  refreshSessions: (agentId: string) => void;
  carryForwardMedia: boolean;
};

export function useAgentsChatMessaging({
  selectedAgent,
  conversationId,
  messages,
  setMessages,
  setSessionTitle,
  refreshSessions,
  carryForwardMedia,
}: Params) {
  const [query, setQuery] = useState("");
  const [pendingMedia, setPendingMedia] = useState<PendingChatMedia[]>([]);
  const [uploadingMedia, setUploadingMedia] = useState(false);
  const [chatting, setChatting] = useState(false);
  const [pendingTool, setPendingTool] = useState<PendingToolCall | null>(null);
  const [pollJobs, setPollJobs] = useState<GenerativePollJob[]>([]);
  const [wsGenerativeMsg, setWsGenerativeMsg] = useState<string | null>(null);
  const [wsGenerativeProgress, setWsGenerativeProgress] = useState<number | null>(null);
  const [wsActiveJobIds, setWsActiveJobIds] = useState<string[]>([]);

  const { wsEnabled, wsReady, client: wsClientRef } = useAgentChatWs(selectedAgent, conversationId);

  const carriedMedia = useMemo((): ChatMessageMedia[] => {
    if (pendingMedia.length > 0 || !carryForwardMedia) return [];
    return lastUserMessageMedia(messages);
  }, [carryForwardMedia, messages, pendingMedia.length]);

  const {
    statusMsg: generativePollMsg,
    progressPercent: generativeProgress,
    cancelJob: cancelGenerativeJob,
    canCancel: canCancelGenerative,
  } = useGenerativeJobPoll(pollJobs, (artifacts) => {
    setMessages((prev) => mergeArtifactsIntoLastAssistant(prev, artifacts));
    setPollJobs([]);
  });

  const mergeGenerativeArtifacts = useCallback(
    (artifacts: Parameters<typeof mergeArtifactsIntoLastAssistant>[1]) => {
      if (!artifacts.length) return;
      setMessages((prev) => mergeArtifactsIntoLastAssistant(prev, artifacts));
    },
    [setMessages],
  );

  const handleWsGenerativeJob = useCallback(
    (job: GenerativeJobOut, phase: "queued" | "progress" | "done") => {
      setWsActiveJobIds((prev) => (prev.includes(job.id) ? prev : [...prev, job.id]));
      if (job.progress_percent != null) setWsGenerativeProgress(job.progress_percent);
      const label = job.progress_message || "生成中…";
      setWsGenerativeMsg(job.progress_percent != null ? `${label}（${job.progress_percent}%）` : label);
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
    (res: ChatAgentResult, optimistic: ChatMessage[], userText: string, userMedia: ChatMessageMedia[], useWsJobs: boolean) => {
      setPendingTool(res.pending_tool ?? null);
      if (!useWsJobs) {
        setPollJobs(collectPendingGenerativeJobs(res));
      } else {
        setPollJobs([]);
        const pendingIds = collectPendingGenerativeJobIds(res);
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
          artifacts: mapResponseArtifacts(res),
          steps: res.steps?.length ? res.steps : undefined,
          traceId: res.trace_id,
        },
      ];
      setMessages(nextMessages);
      appendTurn(selectedAgent, conversationId, userText, res.answer, res.steps ?? [], res.trace_id, userMedia.length ? userMedia : undefined);
      refreshSessions(selectedAgent);
      const updated = getSession(selectedAgent, conversationId);
      if (updated) setSessionTitle(updated.title);
    },
    [conversationId, refreshSessions, selectedAgent, setMessages, setSessionTitle],
  );

  const runWsChat = useCallback(
    async (payload: Parameters<NonNullable<typeof wsClientRef.current>["sendChat"]>[0], optimistic: ChatMessage[]) => {
      if (!wsClientRef.current) throw new Error("WebSocket 未连接");
      let streamText = "";
      setMessages([...optimistic, { role: "assistant", content: "" }]);
      return wsClientRef.current.sendChat(payload, {
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
      });
    },
    [handleWsGenerativeJob, setMessages, wsClientRef],
  );

  const chat = async () => {
    if (!selectedAgent || !conversationId) return;
    const userText = query.trim();
    const pendingPayload: ChatMediaIn[] = pendingMedia.map((m) => ({
      attachment_id: m.attachment_id,
    }));
    const { payload: mediaPayload, carriedFromPrevious } = resolveOutgoingChatMedia(pendingPayload, messages, carryForwardMedia);
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
        const res = await runWsChat(
          {
            query: userText,
            media: mediaPayload.length ? mediaPayload : undefined,
          },
          optimistic,
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
      setMessages([...optimistic, { role: "assistant", content: err }]);
    } finally {
      setChatting(false);
    }
  };

  const confirmPendingTool = async () => {
    if (!selectedAgent || !conversationId || !pendingTool) return;
    setChatting(true);
    const useWs = wsEnabled && wsReady && wsClientRef.current?.connected;
    try {
      let res: ChatAgentResult;
      if (useWs && wsClientRef.current) {
        res = await runWsChat(
          {
            query: "确认执行工具",
            toolConfirmed: true,
            pendingToolSlug: pendingTool.slug,
            pendingToolParams: pendingTool.params,
          },
          messages,
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
        setPollJobs(collectPendingGenerativeJobs(res));
      } else {
        setPollJobs([]);
      }
      setMessages((prev) => {
        const withoutEmptyTail = prev.length && prev[prev.length - 1].role === "assistant" && !prev[prev.length - 1].content ? prev.slice(0, -1) : prev;
        return [
          ...withoutEmptyTail,
          {
            role: "assistant",
            content: res.answer,
            artifacts: mapResponseArtifacts(res),
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

  const chattingStatusLabel = chatting && pendingTool ? (generativeToolBusyLabel(pendingTool.slug) ?? "思考中…") : chatting ? "思考中…" : null;
  const generativeStatusMessage = wsGenerativeMsg ?? generativePollMsg;
  const generativeProgressValue = generativeProgress ?? wsGenerativeProgress;

  const generativeStatusEl = useMemo(
    () =>
      generativeStatusMessage ? (
        <ChatGenerativeStatusBanner
          message={generativeStatusMessage}
          progressPercent={generativeProgressValue}
          canCancel={canCancelGenerative || wsActiveJobIds.length > 0}
          onCancel={handleCancelGenerative}
        />
      ) : null,
    [canCancelGenerative, generativeProgressValue, generativeStatusMessage, handleCancelGenerative, wsActiveJobIds.length],
  );

  const clearComposer = useCallback(() => {
    setQuery("");
    setPendingMedia([]);
  }, []);

  return {
    query,
    setQuery,
    pendingMedia,
    uploadingMedia,
    chatting,
    pendingTool,
    wsEnabled,
    wsReady,
    chattingStatusLabel,
    generativeStatusEl,
    chat,
    confirmPendingTool,
    onPickAttachments,
    removePendingMedia,
    clearComposer,
  };
}

export type AgentsChatMessaging = ReturnType<typeof useAgentsChatMessaging>;
