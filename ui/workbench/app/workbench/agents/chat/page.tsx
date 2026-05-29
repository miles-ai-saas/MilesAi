"use client";

/**
 * 智能体对话工作台（链路 §5，见 `lib/chains.ts`）。
 * 会话：`chat-sessions`；发送：`api.chatAgent`；Trace：`agent-trace` / `agent-steps`。
 */

import { Suspense } from "react";
import { AgentsChatLayout, useAgentsChatPage } from "@/features/agents";

function AgentsChatLoading() {
  return <div className="flex h-[calc(100vh-3.5rem)] items-center justify-center text-ink-muted">加载对话工作台…</div>;
}

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
