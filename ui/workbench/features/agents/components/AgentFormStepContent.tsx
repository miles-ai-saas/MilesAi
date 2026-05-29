"use client";

/** 智能体表单分步内容（链路 §4 agent/a2a meta）。 */
import { AgentFormStepAdvancedSection } from "@/features/agents/components/AgentFormSteps/AgentFormStepAdvancedSection";
import { AgentFormStepBasicSection } from "@/features/agents/components/AgentFormSteps/AgentFormStepBasicSection";
import { AgentFormStepBindingsSection } from "@/features/agents/components/AgentFormSteps/AgentFormStepBindingsSection";
import { AgentFormStepCapabilitiesSection } from "@/features/agents/components/AgentFormSteps/AgentFormStepCapabilitiesSection";
import { AgentFormStepModelSection } from "@/features/agents/components/AgentFormSteps/AgentFormStepModelSection";
import type { AgentFormStepContentProps } from "@/features/agents/components/agent-form-step-types";
import { useAgentFormStepActions } from "@/features/agents/hooks/use-agent-form-step-actions";

export type { AgentFormStepContentProps } from "@/features/agents/components/agent-form-step-types";

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
