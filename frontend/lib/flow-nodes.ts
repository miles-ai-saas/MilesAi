/**
 * 流程画布节点类型与 graph_json 互转（链路 §6，见 `lib/chains.ts`）。
 *
 * 须与后端保持一致：
 * - ``flow_runtime.nodes.registry.NODE_REGISTRY``
 * - ``integrations.langgraph.compiler.SUPPORTED_CANVAS_NODE_TYPES``
 *
 * Handle 约定（与 compiler._gather_node_inputs 对齐）：
 * - TextInput output → query / input
 * - KnowledgeSearch output → hits（targetHandle）
 * - PromptTemplate output → prompt
 * - PlatformTool output → output（工具执行结果 dict）
 * - ConditionBranch sourceHandle → true | false
 */
import type { Node, Edge } from "@xyflow/react";
import type { FlowEdge, FlowGraph, FlowNode } from "./types";

/** 后端 LangGraph 画布编译支持的节点类型 */
export const NODE_PALETTE = [
  { type: "TextInput", label: "文本输入", color: "#3b82f6" },
  { type: "KnowledgeSearch", label: "知识库检索", color: "#10b981" },
  { type: "RelevanceGrade", label: "相关性评分", color: "#a855f7" },
  { type: "ConditionBranch", label: "条件分支", color: "#ec4899" },
  { type: "StaticResponse", label: "固定回复", color: "#78716c" },
  { type: "ParallelJoin", label: "并行汇合", color: "#06b6d4" },
  { type: "PromptTemplate", label: "提示词模板", color: "#8b5cf6" },
  { type: "LLMCall", label: "大模型", color: "#f59e0b" },
  { type: "PlatformTool", label: "平台工具", color: "#0ea5e9" },
  { type: "TextOutput", label: "文本输出", color: "#64748b" },
] as const;

export type NodeType = (typeof NODE_PALETTE)[number]["type"];

const DEFAULT_DATA: Record<NodeType, Record<string, unknown>> = {
  TextInput: { input_key: "query", label: "用户输入" },
  KnowledgeSearch: { top_k: 5, retrieval_mode: "default", label: "知识库检索" },
  RelevanceGrade: {
    label: "相关性评分",
    relevance_threshold: 0.35,
    use_llm_grade: false,
  },
  ConditionBranch: {
    label: "条件分支",
    mode: "has_hits",
    threshold: 0.35,
    keyword: "",
  },
  StaticResponse: {
    label: "固定回复",
    text: "抱歉，未在知识库中找到相关资料，请换个问法试试。",
  },
  ParallelJoin: { label: "并行汇合", merge_strategy: "dict" },
  PromptTemplate: {
    label: "提示词",
    template:
      "基于以下资料回答用户问题。\n\n资料：\n{{检索结果}}\n\n问题：{{用户提问}}",
  },
  LLMCall: { temperature: 0.7, max_tokens: 2048, label: "大模型" },
  PlatformTool: {
    tool_slug: "skill_read_reference",
    label: "平台工具",
    confirmed: true,
    merge_input: true,
    params: {},
  },
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

/** 带相关性评分与兜底分支的 RAG 模板（与 backend rag_flow_with_grade.json 一致） */
export const RAG_TEMPLATE_WITH_GRADE: FlowGraph = {
  nodes: [
    { id: "input_1", type: "TextInput", position: { x: 80, y: 160 }, data: { input_key: "query", label: "用户输入" } },
    { id: "search_1", type: "KnowledgeSearch", position: { x: 300, y: 120 }, data: { top_k: 5, label: "知识库检索" } },
    { id: "grade_1", type: "RelevanceGrade", position: { x: 520, y: 160 }, data: { relevance_threshold: 0.35, use_llm_grade: false, label: "相关性评分" } },
    { id: "prompt_1", type: "PromptTemplate", position: { x: 760, y: 80 }, data: { label: "提示词", template: "基于以下资料回答：\n{{检索结果}}\n\n问题：{{用户提问}}" } },
    { id: "llm_1", type: "LLMCall", position: { x: 1000, y: 80 }, data: { temperature: 0.7, label: "大模型" } },
    { id: "fallback_1", type: "StaticResponse", position: { x: 760, y: 260 }, data: { label: "无命中兜底", text: "抱歉，未找到与「{{用户提问}}」相关的资料。" } },
    { id: "output_1", type: "TextOutput", position: { x: 1240, y: 160 }, data: { label: "输出" } },
  ],
  edges: [
    { source: "input_1", target: "search_1", sourceHandle: "output", targetHandle: "query" },
    { source: "search_1", target: "grade_1", sourceHandle: "output", targetHandle: "hits" },
    { source: "grade_1", target: "prompt_1", sourceHandle: "good", targetHandle: "input" },
    { source: "grade_1", target: "prompt_1", sourceHandle: "poor", targetHandle: "input" },
    { source: "prompt_1", target: "llm_1", sourceHandle: "output", targetHandle: "prompt" },
    { source: "llm_1", target: "output_1", sourceHandle: "output", targetHandle: "input" },
    { source: "grade_1", target: "fallback_1", sourceHandle: "none", targetHandle: "input" },
    { source: "fallback_1", target: "output_1", sourceHandle: "output", targetHandle: "input" },
  ],
};
