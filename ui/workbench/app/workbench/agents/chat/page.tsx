"use client";

/**
 * 智能体对话工作台（链路 §5，见 `lib/chains.ts`）。
 * 会话：`chat-sessions`；发送：`api.chatAgent`；Trace：`agent-trace` / `agent-steps`。
 */

import { Suspense } from "react";
import { AgentsChatLayout, AgentsChatLoading, useAgentsChatPage } from "@/features/agents";

export default function AgentsChatPage() {
  return (
    <Suspense fallback={<AgentsChatLoading />}>
      <AgentsChatMain />
    </Suspense>
  );
}

function AgentsChatMain() {
  const vm = useAgentsChatPage();

  if (!vm.ready || vm.list.loading) {
    return <AgentsChatLoading />;
  }

  return <AgentsChatLayout vm={vm} />;
}
