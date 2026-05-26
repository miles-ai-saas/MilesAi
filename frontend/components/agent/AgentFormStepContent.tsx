"use client";

/** 智能体表单分步内容（链路 §4 agent/a2a meta）。 */
import type { Dispatch, SetStateAction } from "react";
import { formatAgentCode, type AgentFormValues } from "@/components/agent/agent-form-shared";
import { TagPicker } from "@/components/tag/TagPicker";
import { subAgentRoleOptions } from "@/lib/agent-utils";
import { useAgentMeta } from "@/hooks/use-agent-meta";
import { useA2aMeta } from "@/hooks/use-a2a-meta";
import { a2aInvokePolicyOptions } from "@/lib/a2a-labels";
import { useMemo } from "react";
import type {
  Agent,
  A2aPeer,
  Flow,
  KnowledgeBase,
  McpService,
  ModelConfig,
  PromptTemplate,
  SkillPackage,
  SysCategory,
  ToolCatalogItem,
} from "@/lib/types";

type Props = {
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
}: Props) {
  const agentMeta = useAgentMeta();
  const a2aMeta = useA2aMeta();
  const roleOptions = subAgentRoleOptions(agentMeta);
  const invokePolicies = a2aInvokePolicyOptions(a2aMeta);

  const imageGenModels = useMemo(
    () => models.filter((m) => m.is_active !== false && m.model_type === "image_gen"),
    [models],
  );
  const videoGenModels = useMemo(
    () => models.filter((m) => m.is_active !== false && m.model_type === "video_gen"),
    [models],
  );

  const toggleMcp = (id: string) => {
    setForm((f) => ({
      ...f,
      mcp_service_ids: f.mcp_service_ids.includes(id)
        ? f.mcp_service_ids.filter((x) => x !== id)
        : [...f.mcp_service_ids, id],
    }));
  };

  const toggleToolSlug = (slug: string) => {
    setForm((f) => ({
      ...f,
      tool_slugs: f.tool_slugs.includes(slug)
        ? f.tool_slugs.filter((x) => x !== slug)
        : [...f.tool_slugs, slug],
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
      a2a_peers: f.a2a_peers.map((p) =>
        p.peer_id === peerId ? { ...p, trigger_keywords: keywords } : p,
      ),
    }));
  };

  const toggleKb = (id: string) => {
    setForm((f) => ({
      ...f,
      kb_ids: f.kb_ids.includes(id) ? f.kb_ids.filter((x) => x !== id) : [...f.kb_ids, id],
    }));
  };

  const formWidth = designMode ? "max-w-3xl" : "max-w-2xl";

  switch (step) {
    case 0:
      return (
        <div className={`mx-auto ${formWidth} space-y-5`}>
          <label className="block text-sm">
            <span className="mb-1 block text-ink-muted">分类</span>
            <select
              className="input-field w-full"
              value={form.category_id}
              onChange={(e) => setForm((f) => ({ ...f, category_id: e.target.value }))}
            >
              <option value="">未分类</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-ink-muted">标签</span>
            <TagPicker
              value={form.tag_ids}
              onChange={(tag_ids) => setForm((f) => ({ ...f, tag_ids }))}
            />
          </label>
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
          {agentId && (
            <label className="block text-sm">
              <span className="mb-1 flex items-center gap-1 text-ink-muted">
                智能体编号
                <span
                  className="cursor-help text-ink-faint"
                  title="系统根据 ID 生成的展示编号，不可修改"
                >
                  ⓘ
                </span>
              </span>
              <input
                className="input-field w-full bg-surface-muted text-ink-muted"
                readOnly
                value={formatAgentCode(agentId)}
              />
            </label>
          )}
          <label className="block text-sm">
            <span className="mb-1 block text-ink-muted">
              描述 <span className="text-brand">*</span>
            </span>
            <textarea
              className="input-field h-28 w-full"
              placeholder="请输入智能体描述"
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            />
          </label>
        </div>
      );
    case 1:
      return (
        <div className={`mx-auto ${formWidth} space-y-5`}>
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
              className="input-field h-32 w-full font-mono text-sm"
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
            <div className="flex gap-2">
              <select
                className="input-field min-w-0 flex-1"
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
              {form.published_flow_id && onOpenFlowCanvas && (
                <button type="button" className="btn-ghost shrink-0 border border-line" onClick={onOpenFlowCanvas}>
                  画布
                </button>
              )}
            </div>
          </label>
          {form.published_flow_id && form.sub_agents.length === 0 && (
            <p className="text-xs text-ink-muted lg:col-span-2">
              已绑定流程：对话将经 LangGraph 编译执行画布（并行 / 条件分支）。
            </p>
          )}
          <div className="rounded-lg border border-brand/30 bg-brand-light/20 p-4 lg:col-span-2">
            <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-ink">
              <input
                type="checkbox"
                checked={form.enable_tool_calling}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    enable_tool_calling: e.target.checked,
                    tool_slugs: e.target.checked ? f.tool_slugs : [],
                    enable_generative_tools: e.target.checked
                      ? f.enable_generative_tools
                      : false,
                  }))
                }
              />
              启用平台工具自动调用（function calling）
            </label>
            <p className="mt-1 text-xs text-ink-muted">
              与 MCP 独立。未勾选下方工具则允许全部内置 + 自定义 HTTP。生图/生视频亦依赖本项。
            </p>
            <label className="mt-3 flex cursor-pointer items-center gap-2 text-sm text-ink">
              <input
                type="checkbox"
                checked={form.enable_generative_tools}
                disabled={!form.enable_tool_calling}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    enable_generative_tools: e.target.checked,
                    enable_tool_calling: e.target.checked ? true : f.enable_tool_calling,
                  }))
                }
              />
              启用生图 / 生视频工具（万相优先）
            </label>
            <p className="mt-1 text-xs text-ink-muted">
              对话中可调用 generate_image、generate_video；产出出现在回复与「生成素材」。有知识库时须同时开启「平台工具」：将走 knowledge_search + 生成工具，不再使用自动 LangGraph RAG。
            </p>
            {form.enable_generative_tools && form.enable_tool_calling && (
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <label className="block text-xs">
                  <span className="mb-1 block text-ink-muted">生图模型（可选）</span>
                  <select
                    className="input-field w-full text-sm"
                    value={form.generative_image_model_id}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, generative_image_model_id: e.target.value }))
                    }
                  >
                    <option value="">默认（租户 image_gen）</option>
                    {imageGenModels.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name}
                        {!m.has_api_key ? "（缺 Key）" : ""}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-xs">
                  <span className="mb-1 block text-ink-muted">生视频模型（可选）</span>
                  <select
                    className="input-field w-full text-sm"
                    value={form.generative_video_model_id}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, generative_video_model_id: e.target.value }))
                    }
                  >
                    <option value="">默认（租户 video_gen）</option>
                    {videoGenModels.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name}
                        {!m.has_api_key ? "（缺 Key）" : ""}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            )}
            {form.enable_tool_calling && (
              <div className="mt-3 flex max-h-36 flex-wrap gap-2 overflow-y-auto">
                {toolCatalog.length === 0 && (
                  <span className="text-xs text-ink-faint">暂无平台工具，请先在工具页创建</span>
                )}
                {toolCatalog.map((t) => (
                  <label key={`${t.source}-${t.slug}`} className="flex cursor-pointer items-center gap-1 text-xs">
                    <input
                      type="checkbox"
                      checked={form.tool_slugs.includes(t.slug)}
                      onChange={() => toggleToolSlug(t.slug)}
                    />
                    {t.name} ({t.slug})
                  </label>
                ))}
              </div>
            )}
          </div>
          <div className="rounded-lg border border-line-soft p-4 lg:col-span-2">
            <p className="mb-1 text-xs font-medium text-ink-muted">MCP 服务（可多选，仅注入提示词）</p>
            <p className="mb-2 text-xs text-ink-faint">
              MCP 与平台工具分离；绑定后写入系统提示，对话内暂不自动调用。
            </p>
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
            <div className="flex max-h-40 flex-wrap gap-2 overflow-y-auto">
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
            <p className="mb-1 text-xs font-medium text-ink">内部协同（可选，最多 8 个）</p>
            <p className="mb-2 text-xs text-ink-muted">
              绑定同租户其他智能体，由 DeepAgents 做平台内委派；非 A2A 外部协议。
            </p>
            <div className="max-h-48 space-y-2 overflow-y-auto">
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
                          {roleOptions.map((o) => (
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
              已启用内部协同：对话走 DeepAgents 规划，RAG LangGraph 不生效。
            </p>
          )}
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4 lg:col-span-2">
            <p className="mb-1 text-xs font-medium text-ink">引用外部 A2A（可选，最多 4 个）</p>
            <p className="mb-2 text-xs text-ink-muted">
              在保持本地能力的前提下，按规则或规划调用「A2A 互联 → 外部登记」中的 Agent。若需纯外部编排，请创建「A2A 互联宿主」。
            </p>
            {form.a2a_peers.length > 0 && (
              <label className="mb-3 block text-xs">
                <span className="mb-1 block text-ink-muted">外部调用策略</span>
                <select
                  className="input-field w-full max-w-xs py-1.5 text-xs"
                  value={form.a2a_invoke_policy}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      a2a_invoke_policy: e.target.value as typeof f.a2a_invoke_policy,
                    }))
                  }
                >
                  {invokePolicies.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <div className="max-h-56 space-y-2 overflow-y-auto">
              {a2aPeers.length === 0 && (
                <span className="text-xs text-ink-faint">
                  请先在智能体列表 A2A Tab 登记外部 Agent 并同步 Card。
                </span>
              )}
              {a2aPeers.map((p) => {
                const bound = form.a2a_peers.find((x) => x.peer_id === p.id);
                return (
                  <div
                    key={p.id}
                    className="rounded border border-line-soft bg-surface px-2 py-2 text-xs"
                  >
                    <label className="flex cursor-pointer items-center gap-2">
                      <input
                        type="checkbox"
                        checked={Boolean(bound)}
                        onChange={() => toggleA2aPeer(p.id)}
                      />
                      <span className="font-medium text-ink">{p.name}</span>
                      <span className="text-ink-faint">
                        {p.card_display_name ?? "已连通"} · {p.skills_count} skills
                      </span>
                    </label>
                    {bound && (
                      <input
                        className="input-field mt-2 w-full py-1 text-xs"
                        placeholder="规则关键词，逗号分隔（命中则必调此外部 Agent）"
                        value={(bound.trigger_keywords ?? []).join(", ")}
                        onChange={(e) => setA2aKeywords(p.id, e.target.value)}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      );
    case 4:
      return (
        <div className={`mx-auto ${formWidth} space-y-5`}>
          {form.sub_agents.length > 0 ? (
            <div className="rounded-lg border border-line-soft p-4">
              <p className="mb-2 text-xs font-medium text-ink">内部协同规划</p>
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
            <div className="rounded-lg border border-line-soft p-4">
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
}
