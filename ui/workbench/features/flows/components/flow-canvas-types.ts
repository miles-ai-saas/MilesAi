import type { Ref } from "react";
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
