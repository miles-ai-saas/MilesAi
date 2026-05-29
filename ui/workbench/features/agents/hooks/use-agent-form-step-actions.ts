"use client";

import { useMemo } from "react";
import type { Dispatch, SetStateAction } from "react";
import type { AgentFormValues } from "@/features/agents/lib/agent-form-types";
import { subAgentRoleOptions } from "@/features/agents/lib/agent-labels";
import { useAgentMeta } from "@/features/agents/hooks/use-agent-meta";
import { useA2aMeta } from "@/hooks/use-a2a-meta";
import { a2aInvokePolicyOptions } from "@/lib/a2a-labels";
import type { ModelConfig } from "@/lib/types";

export function useAgentFormStepActions(form: AgentFormValues, setForm: Dispatch<SetStateAction<AgentFormValues>>, models: ModelConfig[]) {
  const agentMeta = useAgentMeta();
  const a2aMeta = useA2aMeta();
  const roleOptions = subAgentRoleOptions(agentMeta);
  const invokePolicies = a2aInvokePolicyOptions(a2aMeta);

  const imageGenModels = useMemo(() => models.filter((m) => m.is_active !== false && m.model_type === "image_gen"), [models]);
  const videoGenModels = useMemo(() => models.filter((m) => m.is_active !== false && m.model_type === "video_gen"), [models]);

  const toggleMcp = (id: string) => {
    setForm((f) => ({
      ...f,
      mcp_service_ids: f.mcp_service_ids.includes(id) ? f.mcp_service_ids.filter((x) => x !== id) : [...f.mcp_service_ids, id],
    }));
  };

  const toggleToolSlug = (slug: string) => {
    setForm((f) => ({
      ...f,
      tool_slugs: f.tool_slugs.includes(slug) ? f.tool_slugs.filter((x) => x !== slug) : [...f.tool_slugs, slug],
    }));
  };

  const toggleSubAgent = (id: string) => {
    setForm((f) => {
      const exists = f.sub_agents.find((s) => s.child_agent_id === id);
      if (exists) {
        return { ...f, sub_agents: f.sub_agents.filter((s) => s.child_agent_id !== id) };
      }
      if (f.sub_agents.length >= 8) return f;
      return { ...f, sub_agents: [...f.sub_agents, { child_agent_id: id, role_hint: undefined }] };
    });
  };

  const setSubRole = (id: string, role_hint: string) => {
    setForm((f) => ({
      ...f,
      sub_agents: f.sub_agents.map((s) => (s.child_agent_id === id ? { ...s, role_hint: role_hint || undefined } : s)),
    }));
  };

  const toggleA2aPeer = (peerId: string) => {
    setForm((f) => {
      const exists = f.a2a_peers.find((p) => p.peer_id === peerId);
      if (exists) {
        return { ...f, a2a_peers: f.a2a_peers.filter((p) => p.peer_id !== peerId) };
      }
      if (f.a2a_peers.length >= 4) return f;
      return {
        ...f,
        a2a_peers: [...f.a2a_peers, { peer_id: peerId, trigger_keywords: [], enabled: true }],
      };
    });
  };

  const setA2aKeywords = (peerId: string, raw: string) => {
    const keywords = raw
      .replace(/，/g, ",")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    setForm((f) => ({
      ...f,
      a2a_peers: f.a2a_peers.map((p) => (p.peer_id === peerId ? { ...p, trigger_keywords: keywords } : p)),
    }));
  };

  const toggleKb = (id: string) => {
    setForm((f) => ({
      ...f,
      kb_ids: f.kb_ids.includes(id) ? f.kb_ids.filter((x) => x !== id) : [...f.kb_ids, id],
    }));
  };

  return {
    roleOptions,
    invokePolicies,
    imageGenModels,
    videoGenModels,
    toggleMcp,
    toggleToolSlug,
    toggleSubAgent,
    setSubRole,
    toggleA2aPeer,
    setA2aKeywords,
    toggleKb,
  };
}

export type AgentFormStepActions = ReturnType<typeof useAgentFormStepActions>;
