import type { ReactNode } from "react";
import { agentPlannerLabel, agentRuntimeModeLabel } from "@/lib/agent-labels";
import type { AgentMeta } from "@/lib/types";

export function AgentDetailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 border-b border-line-soft py-3 sm:grid-cols-[7rem_1fr]">
      <dt className="text-xs font-medium text-ink-muted">{label}</dt>
      <dd className="text-sm text-ink">{children}</dd>
    </div>
  );
}

export function formatAgentConfigSummary(cfg: Record<string, unknown>, subs: number, kbCount: number, meta: AgentMeta | null): ReactNode {
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
  if (cfg.skill_package_id) lines.push("已绑定技能包");
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
