"use client";

/** 智能体表单分步内容（链路 §4 agent/a2a meta）。 */
import type { Dispatch, SetStateAction } from "react";
import { AgentFormStepAdvancedSection } from "@/features/agents/components/AgentFormSteps/AgentFormStepAdvancedSection";
import { AgentFormStepBasicSection } from "@/features/agents/components/AgentFormSteps/AgentFormStepBasicSection";
import { AgentFormStepBindingsSection } from "@/features/agents/components/AgentFormSteps/AgentFormStepBindingsSection";
import { AgentFormStepCapabilitiesSection } from "@/features/agents/components/AgentFormSteps/AgentFormStepCapabilitiesSection";
import { AgentFormStepModelSection } from "@/features/agents/components/AgentFormSteps/AgentFormStepModelSection";
import type { AgentFormValues } from "@/features/agents/lib/agent-form-types";
import { useAgentFormStepActions } from "@/features/agents/hooks/use-agent-form-step-actions";
import type { Agent, A2aPeer, Flow, KnowledgeBase, McpService, ModelConfig, PromptTemplate, SkillPackage, SysCategory, ToolCatalogItem } from "@/lib/types";

export type AgentFormStepContentProps = {
  step: number;
  form: AgentFormValues;
  setForm: Dispatch<SetStateAction<AgentFormValues>>;
  agentId?: string;
  agent?: Agent | null;
  categories: SysCategory[];
  kbs: KnowledgeBase[];
  flows: Flow[];
  prompts: PromptTemplate[];
  models: ModelConfig[];
  skills: SkillPackage[];
  mcps: McpService[];
  toolCatalog: ToolCatalogItem[];
  allAgents: Agent[];
  a2aPeers: A2aPeer[];
  designMode?: boolean;
  onOpenFlowCanvas?: () => void;
};

export function agentFormStepWidth(designMode?: boolean) {
  return designMode ? "max-w-3xl" : "max-w-2xl";
}

export function AgentFormStepContent({
  step,
  form,
  setForm,
  agentId,
  agent,
  categories,
  kbs,
  flows,
  prompts,
  models,
  skills,
  mcps,
  toolCatalog,
  allAgents,
  a2aPeers,
  designMode,
  onOpenFlowCanvas,
}: AgentFormStepContentProps) {
  const actions = useAgentFormStepActions(form, setForm, models);

  switch (step) {
    case 0:
      return <AgentFormStepBasicSection form={form} setForm={setForm} agentId={agentId} categories={categories} designMode={designMode} />;
    case 1:
      return <AgentFormStepModelSection form={form} setForm={setForm} models={models} prompts={prompts} designMode={designMode} />;
    case 2:
      return (
        <AgentFormStepCapabilitiesSection
          form={form}
          setForm={setForm}
          flows={flows}
          skills={skills}
          mcps={mcps}
          toolCatalog={toolCatalog}
          onOpenFlowCanvas={onOpenFlowCanvas}
          actions={actions}
        />
      );
    case 3:
      return (
        <AgentFormStepBindingsSection form={form} setForm={setForm} kbs={kbs} allAgents={allAgents} a2aPeers={a2aPeers} agent={agent} actions={actions} />
      );
    case 4:
      return <AgentFormStepAdvancedSection form={form} setForm={setForm} designMode={designMode} />;
    default:
      return null;
  }
}
