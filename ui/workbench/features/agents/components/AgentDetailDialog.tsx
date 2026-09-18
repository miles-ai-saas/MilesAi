"use client";

/** 智能体只读详情（链路 §4 `useAgentMeta`）。 */

import type { ReactNode } from "react";
import { AgentRenameInline } from "@/features/agents/components/AgentRenameInline";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { useAgentDetailDialog, type AgentDetailDialogVm } from "@/features/agents/hooks/use-agent-detail-dialog";
import { agentPlannerLabel, agentRuntimeModeLabel } from "@/features/agents/lib/agent-labels";
import { agentModeLabel, agentStatusLabel, agentTypeLabel, subAgentRoleLabel } from "@/features/agents/lib/agent-utils";
import { skillIdsOf } from "@/features/agents/lib/agent-form-types";
import type { Agent, AgentMeta } from "@/lib/types";

type Props = {
  open: boolean;
  agentId: string | null;
  onClose: () => void;
  onEdit: (agent: Agent) => void;
  onChat: (agent: Agent) => void;
  onDesign: (agent: Agent) => void;
  onRenamed?: () => void;
};

function AgentDetailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 border-b border-line-soft py-3 sm:grid-cols-[7rem_1fr]">
      <dt className="text-xs font-medium text-ink-muted">{label}</dt>
      <dd className="text-sm text-ink">{children}</dd>
    </div>
  );
}

function formatAgentConfigSummary(cfg: Record<string, unknown>, subs: number, kbCount: number, meta: AgentMeta | null): ReactNode {
  const lines: string[] = [];
  if (cfg.runtime_mode) {
    lines.push(`运行模式：${agentRuntimeModeLabel(String(cfg.runtime_mode), meta)}`);
  }
  if (subs > 0) {
    const planner = cfg.planner != null ? String(cfg.planner) : "deepagents";
    lines.push(`规划器：${agentPlannerLabel(planner, meta)}`);
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
  const skillCount = skillIdsOf(cfg).length;
  if (skillCount) lines.push(`技能包：${skillCount} 个`);
  if (cfg.enable_generative_tools) lines.push("生图/生视频工具：已开启");
  if (cfg.carry_forward_media === false) lines.push("多轮识图沿用附图：已关闭");
  if (lines.length === 0) return <span className="text-ink-muted">默认配置</span>;
  return (
    <ul className="list-inside list-disc space-y-0.5 text-ink-muted">
      {lines.map((l) => (
        <li key={l}>{l}</li>
      ))}
    </ul>
  );
}

function AgentDetailDialogBody({ vm, onRenamed }: { vm: AgentDetailDialogVm; onRenamed?: () => void }) {
  const { agent, agentMeta, resolved } = vm;
  if (!agent || !resolved) return null;

  return (
    <dl className="divide-y divide-line-soft">
      <AgentDetailRow label="ID">
        <code className="break-all text-xs text-ink-muted">{agent.id}</code>
      </AgentDetailRow>
      <AgentDetailRow label="名称">
        <AgentRenameInline
          agentId={agent.id}
          name={agent.name}
          onRenamed={(nextName) => {
            vm.renameAgent(nextName);
            onRenamed?.();
          }}
        />
      </AgentDetailRow>
      <AgentDetailRow label="状态">
        <span className={agent.status === "enabled" ? "text-brand" : "text-ink-muted"}>{agentStatusLabel(agent.status, agentMeta)}</span>
      </AgentDetailRow>
      <AgentDetailRow label="类型">{agentTypeLabel(agent, agentMeta)}</AgentDetailRow>
      <AgentDetailRow label="运行方式">{agentModeLabel(agent)}</AgentDetailRow>
      <AgentDetailRow label="描述">{agent.description?.trim() ? agent.description : <span className="text-ink-muted">未填写</span>}</AgentDetailRow>
      <AgentDetailRow label="大模型">{resolved.modelName ?? <span className="text-ink-muted">默认模型</span>}</AgentDetailRow>
      <AgentDetailRow label="提示词模版">{resolved.promptName ?? <span className="text-ink-muted">无</span>}</AgentDetailRow>
      <AgentDetailRow label="系统提示词">
        {agent.system_prompt?.trim() ? (
          <pre className="max-h-32 overflow-auto whitespace-pre-wrap rounded-lg bg-surface-muted p-2 text-xs">{agent.system_prompt}</pre>
        ) : (
          <span className="text-ink-muted">未配置</span>
        )}
      </AgentDetailRow>
      <AgentDetailRow label="编排流程">
        {resolved.flowName ? (
          <span>
            {resolved.flowName}
            <span className="ml-2 text-xs text-ink-muted">（画布设计）</span>
          </span>
        ) : (
          <span className="text-ink-muted">未绑定</span>
        )}
      </AgentDetailRow>
      <AgentDetailRow label="技能包">{resolved.skillNames.length ? resolved.skillNames.join("、") : <span className="text-ink-muted">无</span>}</AgentDetailRow>
      <AgentDetailRow label="MCP 服务">
        {resolved.mcpNames.length > 0 ? (
          <ul className="list-inside list-disc">
            {resolved.mcpNames.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        ) : (
          <span className="text-ink-muted">无</span>
        )}
      </AgentDetailRow>
      <AgentDetailRow label="知识库">
        {resolved.kbNames.length > 0 ? (
          <ul className="list-inside list-disc">
            {resolved.kbNames.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        ) : (
          <span className="text-ink-muted">未绑定</span>
        )}
      </AgentDetailRow>
      <AgentDetailRow label={agent.agent_type === "a2a" ? "成员 Agent" : "引用外部 A2A"}>
        {(agent.a2a_peers?.length ?? 0) > 0 ? (
          <ul className="space-y-2">
            {agent.a2a_peers!.map((p) => (
              <li key={p.id} className="rounded-lg border border-line-soft bg-surface-muted px-3 py-2 text-xs">
                <span className="font-medium text-ink">{p.name}</span>
                {p.card_display_name && <span className="text-ink-muted"> · Card: {p.card_display_name}</span>}
                {(p.trigger_keywords?.length ?? 0) > 0 && <p className="mt-1 text-ink-faint">规则关键词：{p.trigger_keywords.join("、")}</p>}
              </li>
            ))}
          </ul>
        ) : (
          <span className="text-ink-muted">无</span>
        )}
      </AgentDetailRow>
      <AgentDetailRow label="内部协同">
        {(agent.sub_agents?.length ?? 0) > 0 ? (
          <ul className="space-y-2">
            {agent.sub_agents!.map((s) => (
              <li key={s.id} className="rounded-lg border border-line-soft bg-surface-muted px-3 py-2 text-xs">
                <span className="font-medium text-ink">{s.name}</span>
                <span className="mx-2 text-ink-faint">·</span>
                <span className="text-ink-muted">{subAgentRoleLabel(s.role_hint, agentMeta)}</span>
                <span className="mx-2 text-ink-faint">·</span>
                <span className="text-ink-muted">{agentStatusLabel(s.status, agentMeta)}</span>
                {s.description && <p className="mt-1 text-ink-faint line-clamp-2">{s.description}</p>}
              </li>
            ))}
          </ul>
        ) : (
          <span className="text-ink-muted">无</span>
        )}
      </AgentDetailRow>
      <AgentDetailRow label="高级配置">{formatAgentConfigSummary(resolved.cfg, agent.sub_agents?.length ?? 0, agent.kb_ids.length, agentMeta)}</AgentDetailRow>
    </dl>
  );
}

function AgentDetailDialogFooter({
  agent,
  disabled,
  onClose,
  onEdit,
  onChat,
  onDesign,
}: {
  agent: NonNullable<AgentDetailDialogVm["agent"]>;
  disabled: boolean;
  onClose: () => void;
  onEdit: (agent: NonNullable<AgentDetailDialogVm["agent"]>) => void;
  onChat: (agent: NonNullable<AgentDetailDialogVm["agent"]>) => void;
  onDesign: (agent: NonNullable<AgentDetailDialogVm["agent"]>) => void;
}) {
  return (
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
      <button type="button" className="btn-primary" disabled={disabled} title={disabled ? "请先启用智能体" : undefined} onClick={() => onChat(agent)}>
        对话
      </button>
    </div>
  );
}

export function AgentDetailDialog({ open, agentId, onClose, onEdit, onChat, onDesign, onRenamed }: Props) {
  const vm = useAgentDetailDialog(open, agentId);

  return (
    <ResourceDialog
      open={open}
      title="查看智能体"
      size="sheet"
      onClose={onClose}
      footer={
        vm.agent && vm.resolved ? (
          <AgentDetailDialogFooter agent={vm.agent} disabled={vm.resolved.disabled} onClose={onClose} onEdit={onEdit} onChat={onChat} onDesign={onDesign} />
        ) : (
          <button type="button" className="btn-ghost" onClick={onClose}>
            关闭
          </button>
        )
      }
    >
      {vm.loading && <p className="py-8 text-center text-sm text-ink-muted">加载中…</p>}
      {vm.error && <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{vm.error}</p>}
      {vm.agent && !vm.loading && !vm.error && <AgentDetailDialogBody vm={vm} onRenamed={onRenamed} />}
    </ResourceDialog>
  );
}
