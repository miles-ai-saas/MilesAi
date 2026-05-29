"use client";

import { useEffect, useRef, useState } from "react";
import { AgentChatWsClient, isAgentChatWsEnabled } from "@/features/agents/lib/agent-chat-ws";

/** 绑定智能体 + 会话，维持一条对话 WebSocket。 */
export function useAgentChatWs(agentId: string, conversationId: string) {
  const clientRef = useRef<AgentChatWsClient | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!isAgentChatWsEnabled() || !agentId || !conversationId) {
      clientRef.current?.disconnect();
      clientRef.current = null;
      setReady(false);
      return;
    }

    const client = new AgentChatWsClient(agentId, conversationId);
    clientRef.current = client;
    client.connect();

    const tick = setInterval(() => {
      setReady(client.connected);
    }, 200);

    return () => {
      clearInterval(tick);
      client.disconnect();
      clientRef.current = null;
      setReady(false);
    };
  }, [agentId, conversationId]);

  return {
    wsEnabled: isAgentChatWsEnabled(),
    wsReady: ready,
    client: clientRef,
  };
}
