"use client";

/** 智能体创建/编辑多步表单（链路 §3 + §4 agent/a2a meta）。 */

import { useEffect, useState } from "react";
import { AGENT_FORM_STEPS, agentToFormValues, buildAgentConfig, emptyAgentForm, type AgentFormValues } from "@/features/agents/lib/agent-form-types";
import { AgentFormStepContent } from "@/features/agents/components/AgentFormStepContent";
import { AgentFormStepper } from "@/features/agents/components/AgentFormStepper";
import { useAgentFormResources } from "@/features/agents/hooks/use-agent-form-resources";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { api } from "@/lib/api";
import type { Agent } from "@/lib/types";

export type { AgentFormValues } from "@/features/agents/lib/agent-form-types";

type Props = {
  open: boolean;
  title: string;
  agent?: Agent | null;
  onClose: () => void;
  onSaved: () => void;
};

export function AgentFormDialog({ open, title, agent, onClose, onSaved }: Props) {
  const [form, setForm] = useState<AgentFormValues>(emptyAgentForm());
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);

  const { kbs, flows, prompts, models, skills, mcps, toolCatalog, allAgents, a2aPeers, categories } = useAgentFormResources(open, {
    loadToolCatalog: true,
    loadPeers: true,
  });

  const isLastStep = step === AGENT_FORM_STEPS.length - 1;
  const formName = form.name ?? "";
  const canNext = step === 0 ? formName.trim().length > 0 : true;

  useEffect(() => {
    if (!open) return;
    if (agent) {
      setForm(agentToFormValues(agent));
    } else {
      setForm(emptyAgentForm());
    }
  }, [open, agent]);

  const onSubmit = async () => {
    if (!formName.trim()) return;
    setBusy(true);
    try {
      const payload = {
        name: formName.trim(),
        description: (form.description ?? "").trim() || undefined,
        category_id: form.category_id || null,
        tag_ids: form.tag_ids,
        system_prompt: (form.system_prompt ?? "").trim() || undefined,
        kb_ids: form.kb_ids,
        sub_agents: form.sub_agents,
        a2a_peers: form.a2a_peers,
        published_flow_id: form.published_flow_id || null,
        prompt_template_id: form.prompt_template_id || null,
        model_config_id: form.model_config_id || null,
        config: buildAgentConfig(form, agent?.config ?? {}),
      };
      if (agent) {
        await api.updateAgent(agent.id, payload);
      } else {
        await api.createAgent({
          ...payload,
          published_flow_id: form.published_flow_id || undefined,
          prompt_template_id: form.prompt_template_id || undefined,
          model_config_id: form.model_config_id || undefined,
        });
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
    else setStep((s) => Math.min(s + 1, AGENT_FORM_STEPS.length - 1));
  };

  return (
    <ResourceDialog
      open={open}
      title={title}
      size="sheet"
      onClose={onClose}
      footer={
        <div className="flex w-full flex-wrap items-center justify-between gap-3">
          <div className="flex gap-2">
            <button type="button" className="btn-ghost border border-line" disabled={step === 0} onClick={() => setStep((s) => Math.max(0, s - 1))}>
              上一步
            </button>
            <button type="button" className="btn-primary" disabled={busy || !canNext} onClick={goNext}>
              {busy ? "保存中…" : isLastStep ? (agent ? "保存" : "创建") : "下一步"}
            </button>
          </div>
          <div className="flex gap-2">
            <button type="button" className="btn-ghost" onClick={onClose}>
              取消
            </button>
          </div>
        </div>
      }
    >
      <AgentFormStepper step={step} onStepClick={setStep} />
      <div className="mb-4">
        <h3 className="text-base font-semibold text-ink">{AGENT_FORM_STEPS[step].title}</h3>
        <p className="text-xs text-ink-muted">{AGENT_FORM_STEPS[step].subtitle}</p>
      </div>
      <div className="min-h-[min(55vh,480px)]">
        <AgentFormStepContent
          step={step}
          form={form}
          setForm={setForm}
          agent={agent}
          categories={categories}
          kbs={kbs}
          flows={flows}
          prompts={prompts}
          models={models}
          skills={skills}
          mcps={mcps}
          toolCatalog={toolCatalog}
          allAgents={allAgents}
          a2aPeers={a2aPeers}
        />
      </div>
    </ResourceDialog>
  );
}
