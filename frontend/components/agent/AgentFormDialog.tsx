"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { SUB_AGENT_ROLE_OPTIONS } from "@/lib/agent-utils";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import type { SubAgentBindingInput } from "@/lib/types";
import type {
  Agent,
  Flow,
  KnowledgeBase,
  McpService,
  ModelConfig,
  PromptTemplate,
  SkillPackage,
} from "@/lib/types";

export type AgentFormValues = {
  name: string;
  description: string;
  system_prompt: string;
  kb_ids: string[];
  published_flow_id: string;
  prompt_template_id: string;
  model_config_id: string;
  skill_package_id: string;
  mcp_service_ids: string[];
  sub_agents: SubAgentBindingInput[];
  use_langgraph_rag: boolean;
  use_llm_grade: boolean;
  relevance_threshold: number;
  rag_max_retries: number;
  subagent_parallel: boolean;
  force_platform_planner: boolean;
};

const STEPS = [
  { title: "基本信息", subtitle: "配置智能体的名称与描述" },
  { title: "模型与提示词", subtitle: "选择模型和提示词模版" },
  { title: "工具与能力", subtitle: "配置技能包、编排流程与 MCP 服务" },
  { title: "知识库与子智能体", subtitle: "配置知识库与多智能体协同" },
  { title: "高级设置", subtitle: "RAG 工作流与子智能体规划选项" },
] as const;

const emptyForm = (): AgentFormValues => ({
  name: "",
  description: "",
  system_prompt: "",
  kb_ids: [],
  published_flow_id: "",
  prompt_template_id: "",
  model_config_id: "",
  skill_package_id: "",
  mcp_service_ids: [],
  sub_agents: [],
  use_langgraph_rag: true,
  use_llm_grade: false,
  relevance_threshold: 0.35,
  rag_max_retries: 1,
  subagent_parallel: false,
  force_platform_planner: false,
});

type Props = {
  open: boolean;
  title: string;
  agent?: Agent | null;
  onClose: () => void;
  onSaved: () => void;
};

function AgentFormStepper({
  step,
  onStepClick,
}: {
  step: number;
  onStepClick: (index: number) => void;
}) {
  return (
    <nav className="mb-8" aria-label="创建步骤">
      <div className="flex items-center">
        {STEPS.map((s, i) => {
          const done = i < step;
          const active = i === step;
          const lineDone = i < step;
          return (
            <div key={s.title} className="flex min-w-0 flex-1 items-center">
              <button
                type="button"
                onClick={() => onStepClick(i)}
                className="group flex min-w-0 flex-1 flex-col items-center"
              >
                <span
                  className={`relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition ${
                    active
                      ? "bg-brand text-white shadow-sm"
                      : done
                        ? "bg-brand/15 text-brand"
                        : "border border-line bg-surface text-ink-muted group-hover:border-brand/50"
                  }`}
                >
                  {done ? "✓" : i + 1}
                </span>
                <span
                  className={`mt-2 max-w-[5.5rem] truncate text-center text-[10px] leading-tight sm:max-w-none sm:text-[11px] ${
                    active ? "font-medium text-brand" : "text-ink-muted"
                  }`}
                  title={s.title}
                >
                  {s.title}
                </span>
              </button>
              {i < STEPS.length - 1 && (
                <div
                  className={`mx-0.5 mt-[-1.25rem] hidden h-0.5 flex-1 sm:block ${
                    lineDone ? "bg-brand/35" : "bg-line"
                  }`}
                  aria-hidden
                />
              )}
            </div>
          );
        })}
      </div>
    </nav>
  );
}

export function AgentFormDialog({ open, title, agent, onClose, onSaved }: Props) {
  const [form, setForm] = useState<AgentFormValues>(emptyForm);
  const [step, setStep] = useState(0);
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [flows, setFlows] = useState<Flow[]>([]);
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [skills, setSkills] = useState<SkillPackage[]>([]);
  const [mcps, setMcps] = useState<McpService[]>([]);
  const [allAgents, setAllAgents] = useState<Agent[]>([]);
  const [busy, setBusy] = useState(false);

  const isLastStep = step === STEPS.length - 1;
  const canNext = step === 0 ? form.name.trim().length > 0 : true;

  useEffect(() => {
    if (!open) return;
    setStep(0);
    Promise.all([
      api.listKbs(1, 100),
      api.listFlows(1, 100),
      api.listPromptTemplates(1, 100),
      api.listModelConfigs(),
      api.listSkillPackages(1, 100),
      api.listMcpServices(1, 100),
      api.listAgents(1, 100),
    ]).then(([kbRes, flowRes, promptRes, modelRes, skillRes, mcpRes, agentRes]) => {
      setKbs(kbRes.items);
      setFlows(flowRes.items.filter((f) => f.status === "published"));
      setPrompts(promptRes.items);
      setModels(modelRes);
      setSkills(skillRes.items.filter((s) => s.is_active));
      setMcps(mcpRes.items);
      setAllAgents(agentRes.items);
    });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (agent) {
      setForm({
        name: agent.name,
        description: agent.description ?? "",
        system_prompt: agent.system_prompt ?? "",
        kb_ids: agent.kb_ids ?? [],
        published_flow_id: agent.published_flow_id ?? "",
        prompt_template_id: agent.prompt_template_id ?? "",
        model_config_id: agent.model_config_id ?? "",
        skill_package_id: String((agent.config as Record<string, unknown>)?.skill_package_id ?? ""),
        mcp_service_ids: (
          ((agent.config as Record<string, unknown>)?.mcp_service_ids as string[]) ?? []
        ).map(String),
        sub_agents: (agent.sub_agents ?? []).map((s) => ({
          child_agent_id: s.id,
          role_hint: s.role_hint ?? undefined,
        })),
        use_langgraph_rag: (agent.config as Record<string, unknown>)?.use_langgraph_rag !== false,
        relevance_threshold: Number(
          (agent.config as Record<string, unknown>)?.relevance_threshold ?? 0.35,
        ),
        rag_max_retries: Number((agent.config as Record<string, unknown>)?.rag_max_retries ?? 1),
        use_llm_grade: Boolean((agent.config as Record<string, unknown>)?.use_llm_grade),
        subagent_parallel: Boolean(
          (agent.config as Record<string, unknown>)?.subagent_parallel,
        ),
        force_platform_planner: Boolean(
          (agent.config as Record<string, unknown>)?.force_platform_planner,
        ),
      });
    } else {
      setForm(emptyForm());
    }
  }, [open, agent]);

  const toggleMcp = (id: string) => {
    setForm((f) => ({
      ...f,
      mcp_service_ids: f.mcp_service_ids.includes(id)
        ? f.mcp_service_ids.filter((x) => x !== id)
        : [...f.mcp_service_ids, id],
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
      sub_agents: f.sub_agents.map((s) =>
        s.child_agent_id === id ? { ...s, role_hint: role_hint || undefined } : s,
      ),
    }));
  };

  const toggleKb = (id: string) => {
    setForm((f) => ({
      ...f,
      kb_ids: f.kb_ids.includes(id) ? f.kb_ids.filter((x) => x !== id) : [...f.kb_ids, id],
    }));
  };

  const buildConfig = (): Record<string, unknown> => {
    const config: Record<string, unknown> = {
      ...((agent?.config as Record<string, unknown>) ?? {}),
    };
    if (form.skill_package_id) config.skill_package_id = form.skill_package_id;
    else delete config.skill_package_id;
    if (form.mcp_service_ids.length) config.mcp_service_ids = form.mcp_service_ids;
    else delete config.mcp_service_ids;

    if (form.sub_agents.length > 0) {
      config.runtime_mode = "autonomous";
      config.planner = "deepagents";
      config.max_plan_iterations = Number(config.max_plan_iterations ?? 12);
      config.max_subagent_calls = Number(config.max_subagent_calls ?? 20);
      if (form.subagent_parallel) config.subagent_parallel = true;
      else delete config.subagent_parallel;
      if (form.force_platform_planner) config.force_platform_planner = true;
      else delete config.force_platform_planner;
      delete config.use_langgraph_rag;
      delete config.use_llm_grade;
    } else if (form.kb_ids.length > 0) {
      if (form.sub_agents.length === 0 && !form.published_flow_id) {
        delete config.runtime_mode;
      }
      if (form.use_langgraph_rag) delete config.use_langgraph_rag;
      else config.use_langgraph_rag = false;
      config.relevance_threshold = form.relevance_threshold;
      config.rag_max_retries = form.rag_max_retries;
      if (form.use_llm_grade) config.use_llm_grade = true;
      else delete config.use_llm_grade;
    } else {
      if (!form.published_flow_id) delete config.runtime_mode;
      delete config.use_langgraph_rag;
      delete config.relevance_threshold;
      delete config.rag_max_retries;
      delete config.use_llm_grade;
    }

    if (form.published_flow_id) {
      config.runtime_mode = "workflow";
    } else if (config.runtime_mode === "workflow") {
      delete config.runtime_mode;
    }
    return config;
  };

  const onSubmit = async () => {
    if (!form.name.trim()) return;
    setBusy(true);
    try {
      const payload = {
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        system_prompt: form.system_prompt.trim() || undefined,
        kb_ids: form.kb_ids,
        sub_agents: form.sub_agents,
        published_flow_id: form.published_flow_id || null,
        prompt_template_id: form.prompt_template_id || null,
        model_config_id: form.model_config_id || null,
        config: buildConfig(),
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
    else setStep((s) => Math.min(s + 1, STEPS.length - 1));
  };

  const stepContent = () => {
    switch (step) {
      case 0:
        return (
          <div className="mx-auto max-w-2xl space-y-5">
            <label className="block text-sm">
              <span className="mb-1 block text-ink-muted">
                名称 <span className="text-brand">*</span>
              </span>
              <input
                className="input-field w-full"
                placeholder="请输入智能体名称"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-ink-muted">描述</span>
              <textarea
                className="input-field h-24 w-full"
                placeholder="请输入智能体描述（可选）"
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              />
            </label>
          </div>
        );
      case 1:
        return (
          <div className="mx-auto max-w-2xl space-y-5">
            <label className="block text-sm">
              <span className="mb-1 block text-ink-muted">大模型</span>
              <select
                className="input-field w-full"
                value={form.model_config_id}
                onChange={(e) => setForm((f) => ({ ...f, model_config_id: e.target.value }))}
              >
                <option value="">默认模型</option>
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.model_name})
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-ink-muted">提示词模版</span>
              <select
                className="input-field w-full"
                value={form.prompt_template_id}
                onChange={(e) => setForm((f) => ({ ...f, prompt_template_id: e.target.value }))}
              >
                <option value="">无提示词模板</option>
                {prompts.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-ink-muted">系统提示词</span>
              <textarea
                className="input-field h-28 w-full font-mono text-sm"
                placeholder="可选，留空则使用模版或默认"
                value={form.system_prompt}
                onChange={(e) => setForm((f) => ({ ...f, system_prompt: e.target.value }))}
              />
            </label>
          </div>
        );
      case 2:
        return (
          <div className="grid gap-5 lg:grid-cols-2">
            <label className="block text-sm lg:col-span-2">
              <span className="mb-1 block text-ink-muted">技能包</span>
              <select
                className="input-field w-full"
                value={form.skill_package_id}
                onChange={(e) => setForm((f) => ({ ...f, skill_package_id: e.target.value }))}
              >
                <option value="">无技能包</option>
                {skills.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-ink-muted">已发布编排流程</span>
              <select
                className="input-field w-full"
                value={form.published_flow_id}
                onChange={(e) => setForm((f) => ({ ...f, published_flow_id: e.target.value }))}
              >
                <option value="">无流程（直连 / RAG / 子智能体）</option>
                {flows.map((fl) => (
                  <option key={fl.id} value={fl.id}>
                    {fl.name}
                  </option>
                ))}
              </select>
            </label>
            {form.published_flow_id && form.sub_agents.length === 0 && (
              <p className="text-xs text-ink-muted lg:col-span-2">
                已绑定流程：对话将经 LangGraph 编译执行画布（并行 / 条件分支）。
              </p>
            )}
            <div className="rounded-lg border border-line-soft p-4 lg:col-span-2">
              <p className="mb-2 text-xs font-medium text-ink-muted">MCP 服务（可多选）</p>
              <div className="flex max-h-32 flex-wrap gap-2 overflow-y-auto">
                {mcps.length === 0 && <span className="text-xs text-ink-faint">暂无 MCP 服务</span>}
                {mcps.map((m) => (
                  <label key={m.id} className="flex cursor-pointer items-center gap-1 text-xs">
                    <input
                      type="checkbox"
                      checked={form.mcp_service_ids.includes(m.id)}
                      onChange={() => toggleMcp(m.id)}
                    />
                    {m.name} ({m.tools_cache?.length ?? 0})
                  </label>
                ))}
              </div>
            </div>
          </div>
        );
      case 3:
        return (
          <div className="grid gap-5 lg:grid-cols-2">
            <div className="rounded-lg border border-line-soft p-4">
              <p className="mb-2 text-xs font-medium text-ink-muted">知识库（可多选）</p>
              <div className="flex max-h-36 flex-wrap gap-2 overflow-y-auto">
                {kbs.length === 0 && <span className="text-xs text-ink-faint">暂无知识库</span>}
                {kbs.map((kb) => (
                  <label key={kb.id} className="flex cursor-pointer items-center gap-1 text-xs">
                    <input
                      type="checkbox"
                      checked={form.kb_ids.includes(kb.id)}
                      onChange={() => toggleKb(kb.id)}
                    />
                    {kb.name}
                  </label>
                ))}
              </div>
            </div>
            <div className="rounded-lg border border-brand/30 bg-brand-light/30 p-4">
              <p className="mb-1 text-xs font-medium text-ink">子智能体（可选，最多 8 个）</p>
              <p className="mb-2 text-xs text-ink-muted">
                绑定后由 DeepAgents 规划委派；未安装时自动降级平台 JSON 规划。
              </p>
              <div className="max-h-44 space-y-2 overflow-y-auto">
                {allAgents
                  .filter((a) => a.id !== agent?.id)
                  .map((a) => {
                    const bound = form.sub_agents.find((s) => s.child_agent_id === a.id);
                    return (
                      <div
                        key={a.id}
                        className="flex flex-wrap items-center gap-2 rounded border border-line-soft bg-surface px-2 py-1.5"
                      >
                        <label className="flex cursor-pointer items-center gap-1 text-xs">
                          <input
                            type="checkbox"
                            checked={Boolean(bound)}
                            onChange={() => toggleSubAgent(a.id)}
                          />
                          {a.name}
                        </label>
                        {bound && (
                          <select
                            className="input-field py-0.5 text-xs"
                            value={bound.role_hint ?? ""}
                            onChange={(e) => setSubRole(a.id, e.target.value)}
                          >
                            {SUB_AGENT_ROLE_OPTIONS.map((o) => (
                              <option key={o.value || "none"} value={o.value}>
                                {o.label}
                              </option>
                            ))}
                          </select>
                        )}
                      </div>
                    );
                  })}
                {allAgents.filter((a) => a.id !== agent?.id).length === 0 && (
                  <span className="text-xs text-ink-faint">暂无其他智能体可绑定</span>
                )}
              </div>
            </div>
            {form.sub_agents.length > 0 && form.kb_ids.length > 0 && (
              <p className="text-xs text-ink-muted lg:col-span-2">
                已绑定子智能体：对话走 DeepAgents 规划，RAG LangGraph 不生效。
              </p>
            )}
          </div>
        );
      case 4:
        return (
          <div className="mx-auto max-w-2xl space-y-5">
            {form.sub_agents.length > 0 ? (
              <div className="rounded-lg border border-line-soft p-3">
                <p className="mb-2 text-xs font-medium text-ink">子智能体规划</p>
                <label className="mb-2 flex cursor-pointer items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={form.subagent_parallel}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, subagent_parallel: e.target.checked }))
                    }
                  />
                  平台规划路径并行调用子智能体
                </label>
                <label className="flex cursor-pointer items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={form.force_platform_planner}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, force_platform_planner: e.target.checked }))
                    }
                  />
                  强制平台 JSON 规划（跳过 DeepAgents）
                </label>
              </div>
            ) : form.kb_ids.length > 0 ? (
              <div className="rounded-lg border border-line-soft p-3">
                <p className="mb-1 text-xs font-medium text-ink">RAG 工作流（LangGraph）</p>
                <p className="mb-2 text-xs text-ink-muted">
                  检索 → 相关性评估 → 重试或生成；多轮会话可写入 Redis checkpoint。
                </p>
                <label className="mb-3 flex cursor-pointer items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={form.use_langgraph_rag}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, use_langgraph_rag: e.target.checked }))
                    }
                  />
                  启用 LangGraph RAG
                </label>
                <label className="mb-3 flex cursor-pointer items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={form.use_llm_grade}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, use_llm_grade: e.target.checked }))
                    }
                  />
                  LLM 相关性评分（需配置模型）
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <label className="text-xs text-ink-muted">
                    相关性阈值
                    <input
                      type="number"
                      min={0}
                      max={1}
                      step={0.05}
                      className="input-field mt-1 w-full"
                      value={form.relevance_threshold}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          relevance_threshold: Number(e.target.value) || 0.35,
                        }))
                      }
                    />
                  </label>
                  <label className="text-xs text-ink-muted">
                    低分重试次数
                    <input
                      type="number"
                      min={0}
                      max={5}
                      step={1}
                      className="input-field mt-1 w-full"
                      value={form.rag_max_retries}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          rag_max_retries: Math.max(0, Number(e.target.value) || 0),
                        }))
                      }
                    />
                  </label>
                </div>
              </div>
            ) : (
              <p className="text-sm text-ink-muted">
                未绑定知识库或子智能体，本步无额外配置。可在上一步添加知识库或子智能体后再调整 RAG /
                规划选项。
              </p>
            )}
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <ResourceDialog
      open={open}
      title={title}
      size="fullscreen"
      onClose={onClose}
      footer={
        <div className="flex w-full flex-wrap items-center justify-between gap-3">
          <div className="flex gap-2">
            <button
              type="button"
              className="btn-ghost border border-line"
              disabled={step === 0}
              onClick={() => setStep((s) => Math.max(0, s - 1))}
            >
              上一步
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={busy || !canNext}
              onClick={goNext}
            >
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
        <h3 className="text-base font-semibold text-ink">{STEPS[step].title}</h3>
        <p className="text-xs text-ink-muted">{STEPS[step].subtitle}</p>
      </div>
      <div className="min-h-[min(50vh,420px)]">{stepContent()}</div>
    </ResourceDialog>
  );
}
