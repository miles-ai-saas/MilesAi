import type { Dispatch, SetStateAction } from "react";
import type { AgentFormValues } from "@/components/agent/agent-form-shared";
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
