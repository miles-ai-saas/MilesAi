"use client";

/** 流程图只读预览（链路 §6）。 */
import { Background, Controls, MiniMap, ReactFlow, ReactFlowProvider, useEdgesState, useNodesState } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect } from "react";
import { flowNodeTypes } from "@/components/flow/FlowNodeCard";
import { graphToReactFlow } from "@/lib/flow-nodes";
import type { FlowGraph } from "@/lib/types";

type Props = {
  graph: FlowGraph;
  className?: string;
};

function FlowCanvasPreviewInner({ graph, className }: Props) {
  const init = graphToReactFlow(graph);
  const [nodes, setNodes, onNodesChange] = useNodesState(init.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(init.edges);

  useEffect(() => {
    const { nodes: n, edges: e } = graphToReactFlow(graph);
    setNodes(n);
    setEdges(e);
  }, [graph, setNodes, setEdges]);

  return (
    <div className={className ?? "h-full min-h-[280px] w-full"}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnDrag
        zoomOnScroll
        zoomOnPinch
        nodeTypes={flowNodeTypes}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls showInteractive={false} />
        <MiniMap zoomable pannable className="!bg-surface-subtle" />
      </ReactFlow>
    </div>
  );
}

export function FlowCanvasPreview(props: Props) {
  return (
    <ReactFlowProvider>
      <FlowCanvasPreviewInner {...props} />
    </ReactFlowProvider>
  );
}
