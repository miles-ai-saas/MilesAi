"use client";

import { useCallback, useEffect, useState } from "react";
import type { PendingChatMedia } from "@/features/agents/lib/chat-sessions";
import { useAgentsChatComposerMedia } from "@/features/agents/hooks/use-agents-chat-composer-media";
import { useAgentsChatGenerativeStatus } from "@/features/agents/hooks/use-agents-chat-generative-status";
import { useAgentChatWs } from "@/features/agents/hooks/use-agent-chat-ws";
import { prependBusinessContext, type BusinessContext } from "@/features/projects";
import { api } from "@/lib/api";
import { appendTurn, appendAssistantMessage, getSession, type ChatMessage, type ChatMessageMedia } from "@/features/agents/lib/chat-sessions";
import { generativeToolBusyLabel } from "@/lib/generative-tool-ui";
import { resolveOutgoingChatMedia } from "@/features/agents/lib/chat-media-forward";
import type { ChatAgentResult, ChatMediaIn, PendingToolCall } from "@/lib/types";
import type { Dispatch, SetStateAction } from "react";

type Params = {
  selectedAgent: string;
  conversationId: string;
  messages: ChatMessage[];
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>;
  setSessionTitle: (title: string) => void;
  refreshSessions: (agentId: string) => void;
  carryForwardMedia: boolean;
  businessContext?: BusinessContext | null;
  initialPrompt?: string | null;
  generativeImageN?: number;
  generativeVideoDuration?: number;
};

export function useAgentsChatMessaging({
  selectedAgent,
  conversationId,
  messages,
  setMessages,
  setSessionTitle,
  refreshSessions,
  carryForwardMedia,
  businessContext = null,
  initialPrompt,
  generativeImageN,
  generativeVideoDuration,
}: Params) {
  const [query, setQuery] = useState("");
  const [chatting, setChatting] = useState(false);
  const [pendingTool, setPendingTool] = useState<PendingToolCall | null>(null);
  const [promptApplied, setPromptApplied] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    if (promptApplied || !initialPrompt) return;
    setQuery(initialPrompt);
    setPromptApplied(true);
  }, [initialPrompt, promptApplied]);

  const { wsEnabled, wsReady, client: wsClientRef } = useAgentChatWs(selectedAgent, conversationId);

  const media = useAgentsChatComposerMedia({ messages, carryForwardMedia, onError: setApiError });
  const generative = useAgentsChatGenerativeStatus({
    setMessages,
    wsClientRef,
    selectedAgent,
    conversationId,
  });

  const applyChatResponse = useCallback(
    (res: ChatAgentResult, optimistic: ChatMessage[], userText: string, userMedia: ChatMessageMedia[], useWsJobs: boolean) => {
      setPendingTool(res.pending_tool ?? null);
      generative.applyResponseGenerativeJobs(res, useWsJobs);
      const arts = generative.artifactsFromResponse(res);
      const nextMessages: ChatMessage[] = [
        ...optimistic,
        {
          role: "assistant",
          content: res.answer,
          artifacts: arts.length ? arts : undefined,
          steps: res.steps?.length ? res.steps : undefined,
          traceId: res.trace_id,
        },
      ];
      setMessages(nextMessages);
      appendTurn(selectedAgent, conversationId, userText, res.answer, res.steps ?? [], res.trace_id, userMedia.length ? userMedia : undefined, arts.length ? arts : undefined);
      refreshSessions(selectedAgent);
      const updated = getSession(selectedAgent, conversationId);
      if (updated) setSessionTitle(updated.title);
    },
    [conversationId, generative, refreshSessions, selectedAgent, setMessages, setSessionTitle],
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
        onGenerativeJob: generative.handleWsGenerativeJob,
      });
    },
    [generative.handleWsGenerativeJob, setMessages, wsClientRef],
  );

  const buildUserMedia = (
    pendingMedia: PendingChatMedia[],
    carriedMedia: ChatMessageMedia[],
    carriedFromPrevious: boolean,
  ): ChatMessageMedia[] => {
    if (pendingMedia.length) {
      return pendingMedia.map((m) => ({
        attachment_id: m.attachment_id,
        filename: m.filename,
        preview_url: m.preview_url,
      }));
    }
    if (carriedFromPrevious) {
      return carriedMedia.map((m) => ({
        attachment_id: m.attachment_id,
        filename: m.filename,
        preview_url: m.preview_url,
      }));
    }
    return [];
  };

  const chat = async () => {
    if (!selectedAgent || !conversationId) return;
    const userText = query.trim();
    const pendingPayload: ChatMediaIn[] = media.pendingMedia.map((m) => ({
      attachment_id: m.attachment_id,
    }));
    const { payload: mediaPayload, carriedFromPrevious } = resolveOutgoingChatMedia(pendingPayload, messages, carryForwardMedia);
    if (!userText && mediaPayload.length === 0) return;

    const apiQuery = userText ? prependBusinessContext(userText, businessContext) : userText;

    const userMedia = buildUserMedia(media.pendingMedia, media.carriedMedia, carriedFromPrevious);

    setChatting(true);
    setQuery("");
    media.setPendingMedia([]);
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
            query: apiQuery,
            media: mediaPayload.length ? mediaPayload : undefined,
            generativeImageN,
            generativeVideoDuration,
          },
          optimistic,
        );
        applyChatResponse(res, optimistic, userText, userMedia, true);
      } else {
        const res = await api.chatAgent(selectedAgent, apiQuery, {
          conversationId,
          media: mediaPayload.length ? mediaPayload : undefined,
          generativeImageN,
          generativeVideoDuration,
        });
        applyChatResponse(res, optimistic, userText, userMedia, false);
      }
    } catch (e) {
      const err = e instanceof Error ? e.message : "对话失败";
      setApiError(err);
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
            generativeImageN,
            generativeVideoDuration,
          },
          messages,
        );
      } else {
        res = await api.chatAgent(selectedAgent, "确认执行工具", {
          conversationId,
          toolConfirmed: true,
          pendingToolSlug: pendingTool.slug,
          pendingToolParams: pendingTool.params,
          generativeImageN,
          generativeVideoDuration,
        });
      }
      setPendingTool(res.pending_tool ?? null);
      generative.applyResponseGenerativeJobs(res, Boolean(useWs));
      const arts = generative.artifactsFromResponse(res);
      setMessages((prev) => {
        const withoutEmptyTail = prev.length && prev[prev.length - 1].role === "assistant" && !prev[prev.length - 1].content ? prev.slice(0, -1) : prev;
        return [
          ...withoutEmptyTail,
          {
            role: "assistant",
            content: res.answer,
            artifacts: arts.length ? arts : undefined,
            steps: res.steps?.length ? res.steps : undefined,
            traceId: res.trace_id,
          },
        ];
      });
      // 工具确认成功必须落本地，否则切会话后「最后一条成功消息」会丢失
      appendAssistantMessage(
        selectedAgent,
        conversationId,
        res.answer,
        res.steps ?? [],
        res.trace_id,
        arts.length ? arts : undefined,
      );
      refreshSessions(selectedAgent);
      const updated = getSession(selectedAgent, conversationId);
      if (updated) setSessionTitle(updated.title);
    } catch (e) {
      const err = e instanceof Error ? e.message : "工具确认失败";
      setApiError(err);
    } finally {
      setChatting(false);
    }
  };

  const clearComposer = useCallback(() => {
    setQuery("");
    media.clearPendingMedia();
  }, [media]);

  const chattingStatusLabel = chatting && pendingTool ? (generativeToolBusyLabel(pendingTool.slug) ?? "思考中…") : chatting ? "思考中…" : null;

  return {
    query,
    setQuery,
    pendingMedia: media.pendingMedia,
    uploadingMedia: media.uploadingMedia,
    chatting,
    pendingTool,
    wsEnabled,
    wsReady,
    chattingStatusLabel,
    generativeStatusEl: generative.generativeStatusEl,
    cancelGenerativeJobById: generative.cancelJobById,
    onGenerativeJobRetried: generative.handleGenerativeJobRetried,
    apiError,
    clearApiError: () => setApiError(null),
    chat,
    confirmPendingTool,
    onPickAttachments: media.onPickAttachments,
    removePendingMedia: media.removePendingMedia,
    clearComposer,
  };
}

export type AgentsChatMessaging = ReturnType<typeof useAgentsChatMessaging>;
