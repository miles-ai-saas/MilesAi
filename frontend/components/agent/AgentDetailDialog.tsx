"use client";

import { useEffect, useState, type ReactNode } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { api } from "@/lib/api";
import {
  agentModeLabel,
  agentStatusLabel,
  agentTypeLabel,
  subAgentRoleLabel,
} from "@/lib/agent-utils";
import type {
  Agent,
  Flow,
  KnowledgeBase,
  McpService,
  ModelConfig,
  PromptTemplate,
  SkillPackage,
} from "@/lib/types";

type Props = {
  open: boolean;
  agentId: string | null;
  onClose: () => void;
  onEdit: (agent: Agent) => void;
  onChat: (agent: Agent) => void;
  onDesign: (agent: Agent) => void;
};

function DetailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 border-b border-line-soft py-3 sm:grid-cols-[7rem_1fr]">
      <dt className="text-xs font-medium text-ink-muted">{label}</dt>
      <dd className="text-sm text-ink">{children}</dd>
    </div>
  );
}

function formatConfigSummary(
  cfg: Record<string, unknown>,
  subs: number,
  kbCount: number,
): ReactNode {
  const lines: string[] = [];
  if (cfg.runtime_mode) lines.push(`运行模式：${String(cfg.runtime_mode)}`);
  if (subs > 0) {
    lines.push(`规划器：${cfg.planner === "deepagents" ? "DeepAgents" : String(cfg.planner ?? "deepagents")}`);
    if (cfg.subagent_parallel) lines.push("平台规划：并行调用成员智能体");
    if (cfg.force_platform_planner) lines.push("强制平台 JSON 规划");
    if (cfg.max_plan_iterations) lines.push(`最大规划轮次：${cfg.max_plan_iterations}`);
  } else if (kbCount > 0 || cfg.use_langgraph_rag === false) {
    if (cfg.use_langgraph_rag === false) lines.push("RAG：线性 LangChain");
    else lines.push("RAG：LangGraph 工作流");
    if (cfg.use_llm_grade) lines.push("LLM 相关性评分：开启");
    if (cfg.relevance_threshold != null) lines.push(`相关性阈值：${cfg.relevance_threshold}`);
    if (cfg.rag_max_retries != null) lines.push(`低分重试：${cfg.rag_max_retries}`);
  }
  const mcp = cfg.mcp_service_ids as string[] | undefined;
  if (mcp?.length) lines.push(`MCP 服务：${mcp.length} 个`);
  if (cfg.skill_package_id) lines.push("已绑定技能包");
  if (lines.length === 0) return <span className="text-ink-muted">默认配置</span>;
  return (
    <ul className="list-inside list-disc space-y-0.5 text-ink-muted">
      {lines.map((l) => (
        <li key={l}>{l}</li>
      ))}
    </ul>
  );
}

export function AgentDetailDialog({
  open,
  agentId,
  onClose,
  onEdit,
  onChat,
  onDesign,
}: Props) {
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

  const cfg = (agent?.config ?? {}) as Record<string, unknown>;
  const modelName = models.find((m) => m.id === agent?.model_config_id)?.name;
  const promptName = prompts.find((p) => p.id === agent?.prompt_template_id)?.name;
  const flowName = flows.find((f) => f.id === agent?.published_flow_id)?.name;
  const skillId = String(cfg.skill_package_id ?? "");
  const skillName = skills.find((s) => s.id === skillId)?.name;
  const mcpIds = (cfg.mcp_service_ids as string[] | undefined) ?? [];
  const mcpNames = mcps.filter((m) => mcpIds.includes(m.id)).map((m) => m.name);
  const kbNames = kbs.filter((k) => agent?.kb_ids.includes(k.id)).map((k) => k.name);
  const disabled = agent?.status !== "enabled";

  return (
    <ResourceDialog
      open={open}
      title={agent ? `查看智能体 · ${agent.name}` : "查看智能体"}
      size="lg"
      onClose={onClose}
      footer={
        agent ? (
          <div className="flex w-full flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn-ghost border border-line" onClick={onClose}>
                关闭
              </button>
              {agent.agent_type !== "a2a" ? (
                <>
                  <button type="button" className="btn-ghost" onClick={() => onEdit(agent)}>
                    编辑
                  </button>
                  <button type="button" className="btn-ghost" onClick={() => onDesign(agent)}>
                    设计
                  </button>
                </>
              ) : (
                <span className="text-xs text-ink-muted">A2A 宿主请在「A2A 互联」Tab 中编辑</span>
              )}
            </div>
            <button
              type="button"
              className="btn-primary"
              disabled={disabled}
              title={disabled ? "请先启用智能体" : undefined}
              onClick={() => onChat(agent)}
            >
              对话
            </button>
          </div>
        ) : (
          <button type="button" className="btn-ghost" onClick={onClose}>
            关闭
          </button>
        )
      }
    >
      {loading && <p className="py-8 text-center text-sm text-ink-muted">加载中…</p>}
      {error && (
        <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
      {agent && !loading && !error && (
        <dl className="divide-y divide-line-soft">
          <DetailRow label="ID">
            <code className="break-all text-xs text-ink-muted">{agent.id}</code>
          </DetailRow>
          <DetailRow label="状态">
            <span
              className={
                agent.status === "enabled"
                  ? "text-brand"
                  : "text-ink-muted"
              }
            >
              {agentStatusLabel(agent.status)}
            </span>
          </DetailRow>
          <DetailRow label="类型">{agentTypeLabel(agent)}</DetailRow>
          <DetailRow label="运行方式">{agentModeLabel(agent)}</DetailRow>
          <DetailRow label="描述">
            {agent.description?.trim() ? agent.description : (
              <span className="text-ink-muted">未填写</span>
            )}
          </DetailRow>
          <DetailRow label="大模型">
            {modelName ?? (
              <span className="text-ink-muted">默认模型</span>
            )}
          </DetailRow>
          <DetailRow label="提示词模版">
            {promptName ?? <span className="text-ink-muted">无</span>}
          </DetailRow>
          <DetailRow label="系统提示词">
            {agent.system_prompt?.trim() ? (
              <pre className="max-h-32 overflow-auto whitespace-pre-wrap rounded-lg bg-surface-muted p-2 text-xs">
                {agent.system_prompt}
              </pre>
            ) : (
              <span className="text-ink-muted">未配置</span>
            )}
          </DetailRow>
          <DetailRow label="编排流程">
            {flowName ? (
              <span>
                {flowName}
                <span className="ml-2 text-xs text-ink-muted">（画布设计）</span>
              </span>
            ) : (
              <span className="text-ink-muted">未绑定</span>
            )}
          </DetailRow>
          <DetailRow label="技能包">
            {skillName ?? <span className="text-ink-muted">无</span>}
          </DetailRow>
          <DetailRow label="MCP 服务">
            {mcpNames.length > 0 ? (
              <ul className="list-inside list-disc">
                {mcpNames.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            ) : (
              <span className="text-ink-muted">无</span>
            )}
          </DetailRow>
          <DetailRow label="知识库">
            {kbNames.length > 0 ? (
              <ul className="list-inside list-disc">
                {kbNames.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            ) : (
              <span className="text-ink-muted">未绑定</span>
            )}
          </DetailRow>
          <DetailRow label={agent.agent_type === "a2a" ? "成员 Agent" : "引用外部 A2A"}>
            {(agent.a2a_peers?.length ?? 0) > 0 ? (
              <ul className="space-y-2">
                {agent.a2a_peers!.map((p) => (
                  <li
                    key={p.id}
                    className="rounded-lg border border-line-soft bg-surface-muted px-3 py-2 text-xs"
                  >
                    <span className="font-medium text-ink">{p.name}</span>
                    {p.card_display_name && (
                      <span className="text-ink-muted"> · Card: {p.card_display_name}</span>
                    )}
                    {(p.trigger_keywords?.length ?? 0) > 0 && (
                      <p className="mt-1 text-ink-faint">
                        规则关键词：{p.trigger_keywords.join("、")}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <span className="text-ink-muted">无</span>
            )}
          </DetailRow>
          <DetailRow label="内部协同">
            {(agent.sub_agents?.length ?? 0) > 0 ? (
              <ul className="space-y-2">
                {agent.sub_agents!.map((s) => (
                  <li
                    key={s.id}
                    className="rounded-lg border border-line-soft bg-surface-muted px-3 py-2 text-xs"
                  >
                    <span className="font-medium text-ink">{s.name}</span>
                    <span className="mx-2 text-ink-faint">·</span>
                    <span className="text-ink-muted">{subAgentRoleLabel(s.role_hint)}</span>
                    <span className="mx-2 text-ink-faint">·</span>
                    <span className="text-ink-muted">{agentStatusLabel(s.status)}</span>
                    {s.description && (
                      <p className="mt-1 text-ink-faint line-clamp-2">{s.description}</p>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <span className="text-ink-muted">无</span>
            )}
          </DetailRow>
          <DetailRow label="高级配置">
            {formatConfigSummary(cfg, agent.sub_agents?.length ?? 0, agent.kb_ids.length)}
          </DetailRow>
        </dl>
      )}
    </ResourceDialog>
  );
}
