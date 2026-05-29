"use client";

import { useEffect, useState } from "react";
import { AGENT_PLANNER, AGENT_RUNTIME_MODE } from "@/features/agents/lib/agent-config";
import { api } from "@/lib/api";
import { a2aInvokePolicyOptions } from "@/lib/a2a-labels";
import { useA2aMeta } from "@/hooks/use-a2a-meta";
import type { Agent, A2aPeer, A2aPeerRefInput, ModelConfig, PromptTemplate } from "@/lib/types";

export type A2aHostFormValues = {
  name: string;
  description: string;
  system_prompt: string;
  prompt_template_id: string;
  model_config_id: string;
  a2a_peers: A2aPeerRefInput[];
  a2a_invoke_policy: "rules_then_plan" | "rules_only" | "plan_only";
};

export const AGENT_HOST_FORM_STEPS = [
  { title: "基本信息", subtitle: "A2A 互联宿主名称与说明" },
  { title: "编排模型", subtitle: "选择用于任务拆解与汇总的模型" },
  { title: "成员 Agent", subtitle: "绑定外部 A2A Agent 与规则" },
] as const;

const DEFAULT_HOST_PROMPT = "你是 A2A 互联宿主编排器。根据用户问题，从已绑定的外部 Agent 中选择合适的成员委派任务，并综合各成员返回结果给出最终回答。";

export function emptyHostAgentForm(): A2aHostFormValues {
  return {
    name: "",
    description: "",
    system_prompt: DEFAULT_HOST_PROMPT,
    prompt_template_id: "",
    model_config_id: "",
    a2a_peers: [],
    a2a_invoke_policy: "rules_then_plan",
  };
}

export function agentToHostFormValues(agent: Agent): A2aHostFormValues {
  const cfg = (agent.config ?? {}) as Record<string, unknown>;
  return {
    name: agent.name,
    description: agent.description ?? "",
    system_prompt: agent.system_prompt ?? DEFAULT_HOST_PROMPT,
    prompt_template_id: agent.prompt_template_id ?? "",
    model_config_id: agent.model_config_id ?? "",
    a2a_peers: (agent.a2a_peers ?? []).map((p) => ({
      peer_id: p.id,
      role_hint: p.role_hint ?? undefined,
      trigger_keywords: p.trigger_keywords ?? [],
      enabled: p.enabled !== false,
    })),
    a2a_invoke_policy: (cfg.a2a_invoke_policy as A2aHostFormValues["a2a_invoke_policy"]) || "rules_then_plan",
  };
}

export function buildHostAgentConfig(form: A2aHostFormValues, base: Record<string, unknown>): Record<string, unknown> {
  return {
    ...base,
    a2a_invoke_policy: form.a2a_invoke_policy,
    max_a2a_calls_per_turn: Number(base.max_a2a_calls_per_turn ?? 3),
    runtime_mode: AGENT_RUNTIME_MODE.AUTONOMOUS,
    planner: AGENT_PLANNER.A2A_ORCHESTRATOR,
  };
}

type Params = {
  open: boolean;
  agent?: Agent | null;
  onClose: () => void;
  onSaved: () => void;
};

export function useA2aHostFormDialog({ open, agent, onClose, onSaved }: Params) {
  const a2aMeta = useA2aMeta(open);
  const invokePolicies = a2aInvokePolicyOptions(a2aMeta);
  const [form, setForm] = useState<A2aHostFormValues>(emptyHostAgentForm());
  const [step, setStep] = useState(0);
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [a2aPeers, setA2aPeers] = useState<A2aPeer[]>([]);
  const [busy, setBusy] = useState(false);

  const isLastStep = step === AGENT_HOST_FORM_STEPS.length - 1;
  const canNext = step === 0 ? form.name.trim().length > 0 : step === 1 ? Boolean(form.model_config_id) : true;

  useEffect(() => {
    if (!open) return;
    setStep(0);
    Promise.all([api.listPromptTemplates(1, 100), api.listModelConfigs(), api.listA2aPeers(1, 100)]).then(([promptRes, modelRes, a2aRes]) => {
      setPrompts(promptRes.items);
      setModels(modelRes);
      setA2aPeers(a2aRes.items.filter((p) => p.status === "active"));
    });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (agent) setForm(agentToHostFormValues(agent));
    else setForm(emptyHostAgentForm());
  }, [open, agent]);

  const togglePeer = (peerId: string) => {
    setForm((f) => {
      const exists = f.a2a_peers.find((p) => p.peer_id === peerId);
      if (exists) {
        return { ...f, a2a_peers: f.a2a_peers.filter((p) => p.peer_id !== peerId) };
      }
      if (f.a2a_peers.length >= 8) return f;
      return {
        ...f,
        a2a_peers: [...f.a2a_peers, { peer_id: peerId, trigger_keywords: [], enabled: true }],
      };
    });
  };

  const setKeywords = (peerId: string, raw: string) => {
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

  const onSubmit = async () => {
    if (!form.name.trim() || !form.model_config_id || form.a2a_peers.length < 1) return;
    setBusy(true);
    try {
      const payload = {
        agent_type: "a2a" as const,
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        system_prompt: form.system_prompt.trim() || undefined,
        model_config_id: form.model_config_id,
        prompt_template_id: form.prompt_template_id || undefined,
        a2a_peers: form.a2a_peers,
        kb_ids: [] as string[],
        sub_agents: [],
        config: buildHostAgentConfig(form, (agent?.config as Record<string, unknown>) ?? {}),
      };
      if (agent) {
        await api.updateAgent(agent.id, payload);
      } else {
        await api.createAgent(payload);
      }
      onSaved();
      onClose();
    } finally {
      setBusy(false);
    }
  };

  const goNext = () => {
    if (!canNext) return;
    if (isLastStep) void onSubmit();
    else setStep((s) => Math.min(s + 1, AGENT_HOST_FORM_STEPS.length - 1));
  };

  return {
    form,
    setForm,
    step,
    setStep,
    prompts,
    models,
    a2aPeers,
    busy,
    invokePolicies,
    isLastStep,
    canNext,
    goNext,
    togglePeer,
    setKeywords,
    steps: AGENT_HOST_FORM_STEPS,
  };
}

export type A2aHostFormDialogVm = ReturnType<typeof useA2aHostFormDialog>;
