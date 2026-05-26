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
 * - ImageGenerate / VideoGenerate：入 `prompt`/`input`，出 `output`（attachment 元数据 dict）
 * - ImageGenerate 可入 `image_attachment_id`（图生图参考图）
 * - VideoGenerate 可入 `image_attachment_id`（首帧）、`last_frame_attachment_id`（尾帧，首尾帧生视频）
 *
 * 多模态生成节点（``group: generative``）须配置 ``model_config_id``（image_gen / video_gen）；
 * 节点 ``prompt`` 非空时覆盖上游文案。预览/下载走鉴权 attachment content API。
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
  /** 调用 image_gen 模型；输出 { kind, attachment_id, mime_type } */
  { type: "ImageGenerate", label: "生图", color: "#e11d48", group: "generative" },
  /** 调用 video_gen 模型（万相）；运行可能阻塞数分钟 */
  { type: "VideoGenerate", label: "生视频", color: "#7c3aed", group: "generative" },
] as const;

export type NodeType = (typeof NODE_PALETTE)[number]["type"];

export const PALETTE_GROUPS = [
  { key: "flow", label: "流程编排" },
  { key: "generative", label: "多模态生成" },
] as const;

export type PaletteGroupKey = (typeof PALETTE_GROUPS)[number]["key"];

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
  ImageGenerate: {
    label: "生图",
    model_config_id: "",
    size: "1024x1024",
    n: 1,
    prompt: "",
    image_attachment_id: "",
  },
  VideoGenerate: {
    label: "生视频",
    model_config_id: "",
    duration: 5,
    resolution: "720P",
    prompt: "",
    image_attachment_id: "",
    last_frame_attachment_id: "",
  },
};

function paletteGroup(
  item: (typeof NODE_PALETTE)[number],
): PaletteGroupKey {
  return "group" in item && item.group === "generative" ? "generative" : "flow";
}

export function paletteItemsByGroup(group: PaletteGroupKey) {
  return NODE_PALETTE.filter((p) => paletteGroup(p) === group);
}

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
        ...(DEFAULT_DATA[n.type as NodeType] ?? {}),
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
