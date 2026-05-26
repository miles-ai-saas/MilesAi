"use client";

import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useMemo } from "react";
import { ArchitectureGraphNode } from "@/components/agent/architecture/ArchitectureGraphNode";
import type { ArchitectureNodeData } from "@/lib/agent-architecture-graph";

const nodeTypes = { architectureNode: ArchitectureGraphNode };

type Props = {
  nodes: Node<ArchitectureNodeData>[];
  edges: Edge[];
  className?: string;
  minHeight?: number;
};

function ArchitectureGraphViewInner({
  nodes: initialNodes,
  edges: initialEdges,
  className,
  minHeight = 320,
}: Props) {
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
        <MiniMap
          zoomable
          pannable
          className="!bg-surface-subtle !border-line"
          nodeColor={(n) => (n.data?.active ? "#e66432" : "#e2e8f0")}
        />
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
