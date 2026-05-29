"use client";

/** 智能体列表（链路 §3）；配置弹窗 + 分类/标签；对话见 agents/chat（§5）。 */

import { AgentsPageView } from "@/components/agent/AgentsPageView";
import { useAgentsPage } from "@/hooks/use-agents-page";

export default function AgentsPage() {
  const vm = useAgentsPage();
  return <AgentsPageView vm={vm} />;
}
