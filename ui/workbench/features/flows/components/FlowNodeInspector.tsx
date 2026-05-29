"use client";

/** 流程节点属性面板（链路 §6，见 flow-node-schemas.ts）。 */

import type { Node } from "@xyflow/react";
import {
  ConditionBranchInspectorForm,
  ImageGenerateInspectorForm,
  KnowledgeSearchInspectorForm,
  LLMCallInspectorForm,
  ParallelJoinInspectorForm,
  PlatformToolInspectorForm,
  PromptTemplateInspectorForm,
  RelevanceGradeInspectorForm,
  StaticResponseInspectorForm,
  SubFlowInspectorForm,
  TextInputInspectorForm,
  TextOutputInspectorForm,
  VideoGenerateInspectorForm,
  makeLabelField,
  type InspectorFormContext,
} from "@/features/flows/components/FlowInspectorNodeForms";
import type { NodeType } from "@/features/flows/lib/flow-nodes";
import type { KnowledgeBase, ModelConfig, PromptTemplate, ToolCatalogItem } from "@/lib/types";

export type { FlowCompileErrorDetail } from "@/features/flows/lib/flow-run-format";
export { formatCompileErrors, formatFlowSteps } from "@/features/flows/lib/flow-run-format";

interface FlowNodeInspectorProps {
  node: Node | null;
  kbs: KnowledgeBase[];
  models: ModelConfig[];
  prompts: PromptTemplate[];
  toolCatalog: ToolCatalogItem[];
  currentFlowId?: string;
  onChange: (nodeId: string, patch: Record<string, unknown>) => void;
}

function InspectorForm({
  node,
  kbs,
  models,
  prompts,
  toolCatalog,
  currentFlowId,
  onChange,
}: FlowNodeInspectorProps & { node: Node }) {
  const type = node.type as NodeType;
  const data = node.data as Record<string, unknown>;
  const patch = (p: Record<string, unknown>) => onChange(node.id, p);
  const ctx: InspectorFormContext = {
    node,
    data,
    patch,
    labelField: makeLabelField(data, patch),
    kbs,
    models,
    prompts,
    toolCatalog,
    currentFlowId,
  };

  switch (type) {
    case "TextInput":
      return <TextInputInspectorForm {...ctx} />;
    case "RelevanceGrade":
      return <RelevanceGradeInspectorForm {...ctx} />;
    case "StaticResponse":
      return <StaticResponseInspectorForm {...ctx} />;
    case "KnowledgeSearch":
      return <KnowledgeSearchInspectorForm {...ctx} />;
    case "PromptTemplate":
      return <PromptTemplateInspectorForm {...ctx} />;
    case "LLMCall":
      return <LLMCallInspectorForm {...ctx} />;
    case "ConditionBranch":
      return <ConditionBranchInspectorForm {...ctx} />;
    case "ParallelJoin":
      return <ParallelJoinInspectorForm {...ctx} />;
    case "PlatformTool":
      return <PlatformToolInspectorForm {...ctx} />;
    case "SubFlow":
      return <SubFlowInspectorForm {...ctx} />;
    case "TextOutput":
      return <TextOutputInspectorForm {...ctx} />;
    case "ImageGenerate":
      return <ImageGenerateInspectorForm {...ctx} />;
    case "VideoGenerate":
      return <VideoGenerateInspectorForm {...ctx} />;
    default:
      return <p className="text-xs text-ink-muted">节点类型 {String(type)} 暂无属性表单</p>;
  }
}

export function FlowNodeInspector(props: FlowNodeInspectorProps) {
  const { node } = props;
  if (!node) {
    return (
      <aside className="flex w-64 shrink-0 flex-col border-l border-line bg-surface p-3 sm:w-72">
        <p className="text-xs font-semibold uppercase text-ink-faint">节点属性</p>
        <p className="mt-4 text-sm text-ink-muted">选中画布上的节点以编辑配置</p>
      </aside>
    );
  }

  return (
    <aside className="flex w-64 shrink-0 flex-col border-l border-line bg-surface sm:w-72">
      <div className="border-b border-line bg-surface-muted/50 px-3 py-2.5">
        <p className="text-xs font-semibold uppercase text-ink-faint">节点属性</p>
        <p className="mt-1 truncate text-sm font-medium text-ink">{String((node.data as Record<string, unknown>)?.label ?? node.type)}</p>
        <p className="font-mono text-[10px] text-ink-faint">{node.type}</p>
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        <InspectorForm {...props} node={node} />
      </div>
    </aside>
  );
}
