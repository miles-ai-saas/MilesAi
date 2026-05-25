/**
 * 流程画布节点类型与 graph_json 互转。
 *
 * 须与后端保持一致：
 * - ``flow_runtime.nodes.registry.NODE_REGISTRY``
 * - ``integrations.langgraph.compiler.SUPPORTED_CANVAS_NODE_TYPES``
 *
 * Handle 约定（与 compiler._gather_node_inputs 对齐）：
 * - TextInput output → query / input
 * - KnowledgeSearch output → hits（targetHandle）
 * - PromptTemplate output → prompt
 * - ConditionBranch sourceHandle → true | false
 */
import type { Node, Edge } from "@xyflow/react";
import type { FlowEdge, FlowGraph, FlowNode } from "./types";

/** 后端 LangGraph 画布编译支持的节点类型 */
export const NODE_PALETTE = [
  { type: "TextInput", label: "文本输入", color: "#3b82f6" },
  { type: "KnowledgeSearch", label: "知识库检索", color: "#10b981" },
  { type: "ConditionBranch", label: "条件分支", color: "#ec4899" },
  { type: "ParallelJoin", label: "并行汇合", color: "#06b6d4" },
  { type: "PromptTemplate", label: "提示词模板", color: "#8b5cf6" },
  { type: "LLMCall", label: "大模型", color: "#f59e0b" },
  { type: "TextOutput", label: "文本输出", color: "#64748b" },
] as const;

export type NodeType = (typeof NODE_PALETTE)[number]["type"];

const DEFAULT_DATA: Record<NodeType, Record<string, unknown>> = {
  TextInput: { input_key: "query", label: "用户输入" },
  KnowledgeSearch: { top_k: 5, label: "知识库检索" },
  ConditionBranch: {
    label: "条件分支",
    mode: "has_hits",
    threshold: 0.35,
    keyword: "",
  },
  ParallelJoin: { label: "并行汇合", merge_strategy: "dict" },
  PromptTemplate: {
    label: "提示词",
    template:
      "基于以下资料回答用户问题。\n\n资料：\n{{检索结果}}\n\n问题：{{用户提问}}",
  },
  LLMCall: { temperature: 0.7, label: "大模型" },
  TextOutput: { label: "输出" },
};

export function reactFlowToGraph(nodes: Node[], edges: Edge[]): FlowGraph {
  return {
    nodes: nodes.map(
      (n): FlowNode => ({
        id: n.id,
        type: (n.type as string) || "TextInput",
        position: n.position,
        data: (n.data as Record<string, unknown>) || {},
      })
    ),
    edges: edges.map(
      (e): FlowEdge => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle || "output",
        targetHandle: e.targetHandle || "input",
      })
    ),
  };
}

export function graphToReactFlow(graph: FlowGraph): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = (graph.nodes || []).map((n, i) => {
    const palette = NODE_PALETTE.find((p) => p.type === n.type);
    return {
      id: n.id,
      type: n.type,
      position: n.position || { x: 80 + (i % 3) * 220, y: 80 + Math.floor(i / 3) * 120 },
      data: {
        ...DEFAULT_DATA[n.type as NodeType],
        ...n.data,
        label: (n.data?.label as string) || palette?.label || n.type,
      },
    };
  });
  const edges: Edge[] = (graph.edges || []).map((e, i) => ({
    id: e.id || `e-${i}`,
    source: e.source,
    target: e.target,
    sourceHandle: e.sourceHandle,
    targetHandle: e.targetHandle,
  }));
  return { nodes, edges };
}

export function createPaletteNode(type: NodeType, position: { x: number; y: number }): Node {
  const meta = NODE_PALETTE.find((p) => p.type === type)!;
  return {
    id: `${type}-${Date.now()}`,
    type,
    position,
    data: { ...DEFAULT_DATA[type], label: meta.label },
  };
}

export const RAG_TEMPLATE: FlowGraph = {
  nodes: [
    { id: "input_1", type: "TextInput", position: { x: 80, y: 120 }, data: { input_key: "query", label: "用户输入" } },
    { id: "search_1", type: "KnowledgeSearch", position: { x: 320, y: 80 }, data: { top_k: 5, label: "知识库检索" } },
    { id: "prompt_1", type: "PromptTemplate", position: { x: 560, y: 120 }, data: { label: "提示词", template: "基于以下资料回答：\n{{检索结果}}\n\n问题：{{用户提问}}" } },
    { id: "llm_1", type: "LLMCall", position: { x: 800, y: 120 }, data: { temperature: 0.7, label: "大模型" } },
    { id: "output_1", type: "TextOutput", position: { x: 1040, y: 120 }, data: { label: "输出" } },
  ],
  edges: [
    { source: "input_1", target: "search_1", sourceHandle: "output", targetHandle: "query" },
    { source: "input_1", target: "prompt_1", sourceHandle: "output", targetHandle: "query" },
    { source: "search_1", target: "prompt_1", sourceHandle: "output", targetHandle: "hits" },
    { source: "prompt_1", target: "llm_1", sourceHandle: "output", targetHandle: "prompt" },
    { source: "llm_1", target: "output_1", sourceHandle: "output", targetHandle: "input" },
  ],
};
