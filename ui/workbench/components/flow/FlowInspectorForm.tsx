"use client";

import type { Node } from "@xyflow/react";
import {
  StaticResponseInspectorForm,
  TextInputInspectorForm,
  TextOutputInspectorForm,
} from "@/components/flow/FlowInspectorInputForms";
import { PlatformToolInspectorForm, SubFlowInspectorForm } from "@/components/flow/FlowInspectorIntegrationForms";
import { ConditionBranchInspectorForm, ParallelJoinInspectorForm } from "@/components/flow/FlowInspectorLogicForms";
import { ImageGenerateInspectorForm, VideoGenerateInspectorForm } from "@/components/flow/FlowInspectorGenerativeForms";
import {
  KnowledgeSearchInspectorForm,
  LLMCallInspectorForm,
  PromptTemplateInspectorForm,
  RelevanceGradeInspectorForm,
} from "@/components/flow/FlowInspectorRagForms";
import { makeLabelField, type InspectorFormContext } from "@/components/flow/flow-inspector-shared";
import type { NodeType } from "@/lib/flow-nodes";
import type { KnowledgeBase, ModelConfig, PromptTemplate, ToolCatalogItem } from "@/lib/types";

type Props = {
  node: Node;
  kbs: KnowledgeBase[];
  models: ModelConfig[];
  prompts: PromptTemplate[];
  toolCatalog: ToolCatalogItem[];
  currentFlowId?: string;
  onChange: (nodeId: string, patch: Record<string, unknown>) => void;
};

function InspectorForm({ node, kbs, models, prompts, toolCatalog, currentFlowId, onChange }: Props) {
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

export { InspectorForm };
