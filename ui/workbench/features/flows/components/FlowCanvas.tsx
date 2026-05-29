"use client";

import { ReactFlowProvider } from "@xyflow/react";
import { forwardRef, type Ref } from "react";
import { FlowCanvasInner } from "@/features/flows/components/FlowCanvasInner";
import type { FlowGraph, KnowledgeBase, ModelConfig, PromptTemplate, ToolCatalogItem } from "@/lib/types";

export interface FlowCanvasHandle {
  loadGraph: (graph: FlowGraph) => void;
  selectNode: (nodeId: string) => void;
}

export interface FlowCanvasProps {
  initialGraph?: FlowGraph;
  onGraphChange?: (graph: FlowGraph) => void;
  currentFlowId?: string;
  kbs?: KnowledgeBase[];
  models?: ModelConfig[];
  prompts?: PromptTemplate[];
  toolCatalog?: ToolCatalogItem[];
  className?: string;
  /** 供 `next/dynamic` 懒加载场景使用（LoadableComponent 无法转发 ref） */
  canvasRef?: Ref<FlowCanvasHandle>;
}

/**
 * 流程画布（链路 §6）：ReactFlow ↔ flow-nodes；FlowNodeInspector / flow-node-schemas。
 */
export const FlowCanvas = forwardRef<FlowCanvasHandle, FlowCanvasProps>(function FlowCanvas(props, ref) {
  return (
    <ReactFlowProvider>
      <FlowCanvasInner {...props} ref={ref} />
    </ReactFlowProvider>
  );
});

export default FlowCanvas;
