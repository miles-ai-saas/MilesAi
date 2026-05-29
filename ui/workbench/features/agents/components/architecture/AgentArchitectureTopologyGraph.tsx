"use client";

import { useMemo } from "react";
import { ArchitectureGraphView } from "@/features/agents/components/architecture/ArchitectureGraphView";
import { buildTopologyGraph } from "@/features/agents/lib/agent-architecture-graph";
import type { AgentArchitectureAttachments } from "@/lib/types";

type Props = {
  agentName: string;
  primaryPathLabel: string;
  attachments: AgentArchitectureAttachments;
  className?: string;
};

export function AgentArchitectureTopologyGraph({ agentName, primaryPathLabel, attachments, className }: Props) {
  const { nodes, edges } = useMemo(() => buildTopologyGraph(attachments, agentName, primaryPathLabel), [agentName, attachments, primaryPathLabel]);

  const hasAttachments =
    Boolean(attachments.model) ||
    attachments.kbs.length > 0 ||
    attachments.sub_agents.length > 0 ||
    attachments.a2a_peers.length > 0 ||
    Boolean(attachments.flow);

  if (!hasAttachments) {
    return (
      <div className="flex h-full min-h-[200px] items-center justify-center p-6 text-center text-sm text-ink-muted">
        暂无挂载能力，可在「配置」中绑定模型、知识库、子智能体或流程。
      </div>
    );
  }

  return <ArchitectureGraphView nodes={nodes} edges={edges} className={className ?? "h-full w-full"} minHeight={360} />;
}
