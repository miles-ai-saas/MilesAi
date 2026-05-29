"use client";

import { Background, Controls, Handle, MiniMap, Position, ReactFlow, ReactFlowProvider, useEdgesState, useNodesState, type Edge, type Node, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useMemo } from "react";
import type { ArchitectureNodeData } from "@/features/agents/lib/agent-architecture-graph";

function ArchitectureGraphNode({ data }: NodeProps<Node<ArchitectureNodeData>>) {
  const isHub = data.variant === "hub";
  const isStep = data.variant === "step" || !data.variant;
  const active = Boolean(data.active || data.onPath);
  const muted = Boolean(data.muted);

  const shell = isHub
    ? "border-brand/40 bg-brand-light shadow-sm ring-1 ring-brand/20"
    : active
      ? "border-brand/50 bg-brand-light/80"
      : muted
        ? "border-line-soft bg-surface-subtle/60 opacity-60"
        : "border-line bg-surface";

  return (
    <div className={`relative max-w-[200px] rounded-lg border px-3 py-2 text-left ${shell}`} title={data.description ?? undefined}>
      <Handle type="target" position={Position.Top} className="!h-1 !w-1 !border-0 !bg-line" />
      {data.subtitle ? <p className="text-[10px] font-medium uppercase tracking-wide text-ink-faint">{data.subtitle}</p> : null}
      <p className={`truncate text-xs font-medium ${isHub ? "text-brand" : "text-ink"}`}>{data.label}</p>
      {isStep && data.description ? <p className="mt-0.5 line-clamp-2 text-[10px] leading-snug text-ink-faint">{data.description}</p> : null}
      {active && !isHub ? <span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-brand" aria-hidden /> : null}
      <Handle type="source" position={Position.Bottom} className="!h-1 !w-1 !border-0 !bg-line" />
    </div>
  );
}

const nodeTypes = { architectureNode: ArchitectureGraphNode };

type Props = {
  nodes: Node<ArchitectureNodeData>[];
  edges: Edge[];
  className?: string;
  minHeight?: number;
};

function ArchitectureGraphViewInner({ nodes: initialNodes, edges: initialEdges, className, minHeight = 320 }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  const proOptions = useMemo(() => ({ hideAttribution: true }), []);

  return (
    <div className={className} style={{ minHeight }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnDrag
        zoomOnScroll
        zoomOnPinch
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={proOptions}
      >
        <Background gap={16} size={1} />
        <Controls showInteractive={false} className="!shadow-sm" />
        <MiniMap zoomable pannable className="!bg-surface-subtle !border-line" nodeColor={(n) => (n.data?.active ? "#e66432" : "#e2e8f0")} />
      </ReactFlow>
    </div>
  );
}

export function ArchitectureGraphView(props: Props) {
  return (
    <ReactFlowProvider>
      <ArchitectureGraphViewInner {...props} />
    </ReactFlowProvider>
  );
}
