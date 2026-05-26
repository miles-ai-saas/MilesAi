/**
 * 流程节点 Handle 与属性面板 schema（链路 §6）。
 * 须与 backend compiler._gather_node_inputs、flow-orchestration-enhancement.md §4.4 一致。
 */
import type { NodeType } from "./flow-nodes";

export const NODE_HANDLES: Record<
  NodeType,
  { targets: string[]; sources: string[] }
> = {
  TextInput: { targets: [], sources: ["output"] },
  KnowledgeSearch: { targets: ["query"], sources: ["output"] },
  RelevanceGrade: { targets: ["hits", "input"], sources: ["good", "poor", "none"] },
  StaticResponse: { targets: ["input"], sources: ["output"] },
  PromptTemplate: { targets: ["query", "hits"], sources: ["output"] },
  LLMCall: { targets: ["prompt", "input"], sources: ["output"] },
  ConditionBranch: { targets: ["hits", "input"], sources: ["true", "false"] },
  ParallelJoin: { targets: ["input"], sources: ["output"] },
  PlatformTool: { targets: ["input", "query", "hits"], sources: ["output"] },
  TextOutput: { targets: ["input"], sources: [] },
};

export const CONDITION_MODES = [
  { value: "has_hits", label: "检索有命中" },
  { value: "score_above", label: "最高分 ≥ 阈值" },
  { value: "text_contains", label: "文本包含关键词" },
  { value: "not_empty", label: "上游文本非空" },
] as const;

export const MERGE_STRATEGIES = [
  { value: "dict", label: "字典合并" },
  { value: "concat_text", label: "文本拼接" },
  { value: "first", label: "取第一个" },
] as const;

const TARGET_HANDLE_COLORS: Record<string, string> = {
  input: "!bg-slate-400",
  query: "!bg-blue-400",
  hits: "!bg-green-400",
  prompt: "!bg-violet-400",
};

const SOURCE_HANDLE_COLORS: Record<string, string> = {
  output: "!bg-slate-600",
  true: "!bg-emerald-500",
  false: "!bg-rose-500",
  good: "!bg-emerald-500",
  poor: "!bg-amber-500",
  none: "!bg-rose-500",
};

export function getNodeHandles(type: string | undefined): {
  targets: string[];
  sources: string[];
} {
  if (type && type in NODE_HANDLES) {
    return NODE_HANDLES[type as NodeType];
  }
  return { targets: ["input"], sources: ["output"] };
}

export function targetHandleClass(id: string): string {
  return TARGET_HANDLE_COLORS[id] ?? "!bg-slate-400";
}

export function sourceHandleClass(id: string): string {
  return SOURCE_HANDLE_COLORS[id] ?? "!bg-slate-600";
}

/** 连线软校验：targetHandle 是否允许 */
export function isValidConnection(
  sourceType: string | undefined,
  sourceHandle: string | null | undefined,
  targetType: string | undefined,
  targetHandle: string | null | undefined,
): boolean {
  const src = getNodeHandles(sourceType);
  const tgt = getNodeHandles(targetType);
  const sh = sourceHandle || "output";
  const th = targetHandle || "input";
  return src.sources.includes(sh) && tgt.targets.includes(th);
}
