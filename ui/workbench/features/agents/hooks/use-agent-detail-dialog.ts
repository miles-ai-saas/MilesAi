"use client";

import { useEffect, useMemo, useState } from "react";
import { useAgentFormResources } from "@/features/agents/hooks/use-agent-form-resources";
import { useAgentMeta } from "@/features/agents/hooks/use-agent-meta";
import type { Agent, AgentConfig } from "@/lib/types";

export function useAgentDetailDialog(open: boolean, agentId: string | null) {
  const agentMeta = useAgentMeta(open);
  const [error, setError] = useState("");

  const { kbs, flows, prompts, models, skills, mcps, agent, loading } = useAgentFormResources(open && Boolean(agentId), {
    loadAgent: agentId ?? undefined,
  });

  useEffect(() => {
    if (!open || !agentId) {
      setError("");
    }
  }, [open, agentId]);

  const resolved = useMemo(() => {
    if (!agent) return null;
    const cfg = (agent.config ?? {}) as AgentConfig;
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
