"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useAgentMeta } from "@/hooks/use-agent-meta";
import type { Agent, Flow, KnowledgeBase, McpService, ModelConfig, PromptTemplate, SkillPackage } from "@/lib/types";

export function useAgentDetailDialog(open: boolean, agentId: string | null) {
  const agentMeta = useAgentMeta(open);
  const [agent, setAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [flows, setFlows] = useState<Flow[]>([]);
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [skills, setSkills] = useState<SkillPackage[]>([]);
  const [mcps, setMcps] = useState<McpService[]>([]);

  useEffect(() => {
    if (!open || !agentId) {
      setAgent(null);
      setError("");
      return;
    }
    setLoading(true);
    setError("");
    Promise.all([
      api.getAgent(agentId),
      api.listKbs(1, 100),
      api.listFlows(1, 100),
      api.listPromptTemplates(1, 100),
      api.listModelConfigs(),
      api.listSkillPackages(1, 100),
      api.listMcpServices(1, 100),
    ])
      .then(([a, kbRes, flowRes, promptRes, modelRes, skillRes, mcpRes]) => {
        setAgent(a);
        setKbs(kbRes.items);
        setFlows(flowRes.items);
        setPrompts(promptRes.items);
        setModels(modelRes);
        setSkills(skillRes.items);
        setMcps(mcpRes.items);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [open, agentId]);

  const resolved = useMemo(() => {
    if (!agent) return null;
    const cfg = (agent.config ?? {}) as Record<string, unknown>;
    const skillId = String(cfg.skill_package_id ?? "");
    const mcpIds = (cfg.mcp_service_ids as string[] | undefined) ?? [];
    return {
      cfg,
      modelName: models.find((m) => m.id === agent.model_config_id)?.name,
      promptName: prompts.find((p) => p.id === agent.prompt_template_id)?.name,
      flowName: flows.find((f) => f.id === agent.published_flow_id)?.name,
      skillName: skills.find((s) => s.id === skillId)?.name,
      mcpNames: mcps.filter((m) => mcpIds.includes(m.id)).map((m) => m.name),
      kbNames: kbs.filter((k) => agent.kb_ids.includes(k.id)).map((k) => k.name),
      disabled: agent.status !== "enabled",
    };
  }, [agent, models, prompts, flows, skills, mcps, kbs]);

  const renameAgent = (nextName: string) => {
    setAgent((prev) => (prev ? { ...prev, name: nextName } : prev));
  };

  return {
    agentMeta,
    agent,
    loading,
    error,
    resolved,
    renameAgent,
  };
}

export type AgentDetailDialogVm = ReturnType<typeof useAgentDetailDialog>;
