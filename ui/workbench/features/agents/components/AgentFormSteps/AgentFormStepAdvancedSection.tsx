"use client";

import { agentFormStepWidth, type AgentFormStepContentProps } from "@/features/agents/components/agent-form-step-types";

type Props = Pick<AgentFormStepContentProps, "form" | "setForm" | "designMode">;

export function AgentFormStepAdvancedSection({ form, setForm, designMode }: Props) {
  return (
    <div className={`mx-auto ${agentFormStepWidth(designMode)} space-y-5`}>
      {form.sub_agents.length > 0 ? (
        <div className="rounded-lg border border-line-soft p-4">
          <p className="mb-2 text-xs font-medium text-ink">内部协同规划</p>
          <label className="mb-2 flex cursor-pointer items-center gap-2 text-xs">
            <input type="checkbox" checked={form.subagent_parallel} onChange={(e) => setForm((f) => ({ ...f, subagent_parallel: e.target.checked }))} />
            平台规划路径并行调用子智能体
          </label>
          <label className="flex cursor-pointer items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={form.force_platform_planner}
              onChange={(e) => setForm((f) => ({ ...f, force_platform_planner: e.target.checked }))}
            />
            强制平台 JSON 规划（跳过 DeepAgents）
          </label>
        </div>
      ) : form.kb_ids.length > 0 ? (
        <div className="rounded-lg border border-line-soft p-4">
          <p className="mb-1 text-xs font-medium text-ink">RAG 工作流（LangGraph）</p>
          <p className="mb-2 text-xs text-ink-muted">检索 → 相关性评估 → 重试或生成；多轮会话可写入 Redis checkpoint。</p>
          <label className="mb-3 flex cursor-pointer items-center gap-2 text-xs">
            <input type="checkbox" checked={form.use_langgraph_rag} onChange={(e) => setForm((f) => ({ ...f, use_langgraph_rag: e.target.checked }))} />
            启用 LangGraph RAG
          </label>
          <label className="mb-3 flex cursor-pointer items-center gap-2 text-xs">
            <input type="checkbox" checked={form.use_llm_grade} onChange={(e) => setForm((f) => ({ ...f, use_llm_grade: e.target.checked }))} />
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
        <p className="text-sm text-ink-muted">未绑定知识库或子智能体，本步无额外配置。可在上一步添加知识库或子智能体后再调整 RAG / 规划选项。</p>
      )}
    </div>
  );
}
