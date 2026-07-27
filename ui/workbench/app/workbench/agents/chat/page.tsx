"use client";

/**
 * 智能体对话工作台（链路 §5，见 `lib/chains.ts`）。
 * 会话：`chat-sessions`；发送：`api.chatAgent`；Trace：`agent-trace` / `agent-steps`。
 */

import { Suspense } from "react";
import { AgentsChatLayout, ApiErrorDialog, useAgentsChatPage } from "@/features/agents";

function AgentsChatLoading() {
  return <div className="flex h-full min-h-0 flex-1 items-center justify-center text-ink-muted">加载对话工作台…</div>;
}

export default function AgentsChatPage() {
  return (
    <div className="flex h-full min-h-0 w-full flex-1 flex-col overflow-hidden">
      <Suspense fallback={<AgentsChatLoading />}>
        <AgentsChatMain />
      </Suspense>
    </div>
  );
}

function AgentsChatMain() {
  const vm = useAgentsChatPage();

  // 鉴权未完成才全屏等待；有 URL agent 或已选出智能体后不再因 list 刷新回到 loading（避免 remount 循环）
  if (!vm.ready) {
    return <AgentsChatLoading />;
  }
  if (!vm.selectedAgent && vm.list.loading) {
    return <AgentsChatLoading />;
  }

  return (
    <>
      <AgentsChatLayout vm={vm} />
      <ApiErrorDialog
        open={!!vm.apiError}
        message={vm.apiError ?? ""}
        onClose={vm.clearApiError}
      />
    </>
  );
}
