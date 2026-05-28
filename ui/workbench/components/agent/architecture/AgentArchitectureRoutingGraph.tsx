"use client";

import { useMemo } from "react";
import { ArchitectureGraphView } from "@/components/agent/architecture/ArchitectureGraphView";
import { buildRoutingGraph } from "@/lib/agent-architecture-graph";
import type { AgentArchitectureDecisionStep } from "@/lib/types";

type Props = {
  steps: AgentArchitectureDecisionStep[];
  className?: string;
};

export function AgentArchitectureRoutingGraph({ steps, className }: Props) {
  const { nodes, edges } = useMemo(() => buildRoutingGraph(steps), [steps]);

  return <ArchitectureGraphView nodes={nodes} edges={edges} className={className ?? "h-full w-full"} minHeight={Math.max(280, nodes.length * 80)} />;
}
