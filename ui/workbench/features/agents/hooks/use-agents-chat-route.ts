"use client";

import { useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { type AgentsChatQuery, buildAgentsChatHref, replaceAgentsChat } from "@/features/agents/lib/agents-chat-href";

/**
 * 对话页 URL 状态机：?agent / ?conv 是唯一真相。
 * - 无 agent：空态
 * - 仅 agent：会话列表
 * - agent + conv：打开会话
 */
export function useAgentsChatRoute() {
  const searchParams = useSearchParams();
  const agentId = searchParams.get("agent") ?? "";
  const conversationId = searchParams.get("conv") ?? "";
  const tab = searchParams.get("tab");
  const prompt = searchParams.get("prompt");

  const currentQuery = useCallback((): AgentsChatQuery => {
    // 以地址栏为准，避免 Suspense remount 后 searchParams 瞬间滞后
    if (typeof window !== "undefined") {
      const s = new URLSearchParams(window.location.search);
      return {
        agent: s.get("agent"),
        conv: s.get("conv"),
        tab: s.get("tab"),
        prompt: s.get("prompt"),
      };
    }
    return { agent: agentId || null, conv: conversationId || null, tab, prompt };
  }, [agentId, conversationId, tab, prompt]);

  const replaceQuery = useCallback(
    (patch: AgentsChatQuery) => {
      const base = currentQuery();
      replaceAgentsChat({
        agent: patch.agent !== undefined ? patch.agent : base.agent,
        conv: patch.conv !== undefined ? patch.conv : base.conv,
        tab: patch.tab !== undefined ? patch.tab : base.tab,
        prompt: patch.prompt !== undefined ? patch.prompt : base.prompt,
      });
    },
    [currentQuery],
  );

  /** 选智能体：只写 agent，清掉 conv。 */
  const selectAgent = useCallback(
    (id: string) => {
      replaceQuery({ agent: id || null, conv: null });
    },
    [replaceQuery],
  );

  /** 选/新建会话：写入 conv（须已有 agent）。 */
  const selectConversation = useCallback(
    (convId: string) => {
      const agent = agentId || currentQuery().agent;
      if (!agent) return;
      replaceQuery({ agent, conv: convId || null });
    },
    [agentId, currentQuery, replaceQuery],
  );

  /** 取消会话选中：保留 agent。 */
  const clearConversation = useCallback(() => {
    const agent = agentId || currentQuery().agent;
    replaceQuery({ agent: agent || null, conv: null });
  }, [agentId, currentQuery, replaceQuery]);

  return {
    agentId,
    conversationId,
    tab,
    prompt,
    replaceQuery,
    selectAgent,
    selectConversation,
    clearConversation,
    hrefFor: buildAgentsChatHref,
  };
}

export type AgentsChatRoute = ReturnType<typeof useAgentsChatRoute>;
