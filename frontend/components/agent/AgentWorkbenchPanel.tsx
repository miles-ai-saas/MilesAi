"use client";

/** 对话页工作台 Tab 面板容器（链路 §5）。 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AGENT_FORM_STEPS,
  agentToFormValues,
  buildAgentConfig,
  emptyAgentForm,
  type AgentFormValues,
} from "@/components/agent/agent-form-shared";
import type { AgentWorkbenchTab } from "@/components/agent/agent-workbench-tabs";
import { AgentFormStepContent } from "@/components/agent/AgentFormStepContent";
import { AgentFormStepper } from "@/components/agent/AgentFormStepper";
import { api } from "@/lib/api";
import type {
  Agent,
  Flow,
  KnowledgeBase,
  McpService,
  ModelConfig,
  PromptTemplate,
  SkillPackage,
  A2aPeer,
  SysCategory,
  ToolCatalogItem,
} from "@/lib/types";

type Props = {
  agentId: string | null;
  /** 名称变更时触发重新拉取（与 agentId 解耦的展示字段） */
  agentName?: string | null;
  activeTab: AgentWorkbenchTab;
  onSaved?: () => void;
};

export function AgentWorkbenchPanel({ agentId, agentName, activeTab, onSaved }: Props) {
  const router = useRouter();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [form, setForm] = useState<AgentFormValues>(emptyAgentForm());
  const [step, setStep] = useState(0);
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [flows, setFlows] = useState<Flow[]>([]);
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [skills, setSkills] = useState<SkillPackage[]>([]);
  const [mcps, setMcps] = useState<McpService[]>([]);
  const [allAgents, setAllAgents] = useState<Agent[]>([]);
  const [a2aPeers, setA2aPeers] = useState<A2aPeer[]>([]);
  const [categories, setCategories] = useState<SysCategory[]>([]);
  const [toolCatalog, setToolCatalog] = useState<ToolCatalogItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);

  const isLastStep = step === AGENT_FORM_STEPS.length - 1;
  const canNext = step === 0 ? form.name.trim().length > 0 : true;

  useEffect(() => {
    if (!agentId) {
      setAgent(null);
      setForm(emptyAgentForm());
      return;
    }
    setStep(0);
    setLoading(true);
    Promise.all([
      api.getAgent(agentId),
      api.listKbs(1, 100),
      api.listFlows(1, 100),
      api.listPromptTemplates(1, 100),
      api.listModelConfigs(),
      api.listSkillPackages(1, 100),
      api.listMcpServices(1, 100),
      api.listAgents(1, 100),
      api.listA2aPeers(1, 100),
      api.listCategories("agent"),
      api.listToolCatalog(),
    ])
      .then(([fresh, kbRes, flowRes, promptRes, modelRes, skillRes, mcpRes, agentRes, a2aRes, catRes, catalogRes]) => {
        setAgent(fresh);
        setForm(agentToFormValues(fresh));
        setKbs(kbRes.items);
        setFlows(flowRes.items.filter((f) => f.status === "published"));
        setPrompts(promptRes.items);
        setModels(modelRes);
        setSkills(skillRes.items.filter((s) => s.is_active));
        setMcps(mcpRes.items);
        setAllAgents(agentRes.items);
        setA2aPeers(a2aRes.items.filter((p) => p.status === "active"));
        setCategories(catRes);
        setToolCatalog(catalogRes);
      })
      .finally(() => setLoading(false));
  }, [agentId, agentName]);

  const onSubmit = async () => {
    if (!agent || !form.name.trim()) return;
    setBusy(true);
    try {
      await api.updateAgent(agent.id, {
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        system_prompt: form.system_prompt.trim() || undefined,
        kb_ids: form.kb_ids,
        sub_agents: form.sub_agents,
        a2a_peers: form.a2a_peers,
        published_flow_id: form.published_flow_id || null,
        prompt_template_id: form.prompt_template_id || null,
        model_config_id: form.model_config_id || null,
        config: buildAgentConfig(form, agent.config as Record<string, unknown>),
      });
      const fresh = await api.getAgent(agent.id);
      setAgent(fresh);
      setForm(agentToFormValues(fresh));
      onSaved?.();
    } finally {
      setBusy(false);
    }
  };

  const goNext = () => {
    if (!canNext) return;
    if (isLastStep) void onSubmit();
    else setStep((s) => Math.min(s + 1, AGENT_FORM_STEPS.length - 1));
  };

  const openFlowCanvas = () => {
    if (form.published_flow_id) {
      router.push(`/workbench/flows/${form.published_flow_id}/edit`);
    }
  };

  if (!agentId) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-center text-sm text-ink-muted">
        请从左侧选择智能体
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-sm text-ink-muted">
        加载中…
      </div>
    );
  }

  if (activeTab === "config") {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto px-8 py-6">
          <AgentFormStepper step={step} onStepClick={setStep} designMode />
          <div className="mb-5">
            <h3 className="text-sm font-medium text-ink">{AGENT_FORM_STEPS[step].title}</h3>
            <p className="mt-0.5 text-xs text-ink-faint">{AGENT_FORM_STEPS[step].subtitle}</p>
          </div>
          <AgentFormStepContent
            step={step}
            form={form}
            setForm={setForm}
            agentId={agentId}
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
            designMode
            onOpenFlowCanvas={openFlowCanvas}
          />
        </div>
        <footer className="flex shrink-0 items-center justify-between gap-4 border-t border-line-soft bg-surface-subtle/60 px-8 py-3">
          <button
            type="button"
            className="btn-sm-outline"
            disabled={step === 0 || busy}
            onClick={() => setStep((s) => Math.max(0, s - 1))}
          >
            上一步
          </button>
          <span className="text-[11px] tabular-nums text-ink-faint">
            {step + 1} / {AGENT_FORM_STEPS.length}
          </span>
          <div className="flex items-center gap-2">
            {!isLastStep && (
              <button
                type="button"
                className="btn-sm-ghost"
                disabled={busy || !form.name.trim()}
                onClick={() => void onSubmit()}
              >
                保存
              </button>
            )}
            <button
              type="button"
              className="btn-sm-primary min-w-[4.5rem]"
              disabled={busy || !canNext}
              onClick={goNext}
            >
              {busy ? "…" : isLastStep ? "完成" : "下一步"}
            </button>
          </div>
        </footer>
      </div>
    );
  }

  return (
    <div className="flex flex-1 items-center justify-center p-6 text-sm text-ink-muted">
      该模块即将推出
    </div>
  );
}
