"use client";

import type { AgentFormStepActions } from "@/features/agents/hooks/use-agent-form-step-actions";
import type { AgentFormStepContentProps } from "@/features/agents/components/agent-form-step-types";

type Props = Pick<AgentFormStepContentProps, "form" | "setForm" | "kbs" | "allAgents" | "a2aPeers" | "agent"> & {
  actions: AgentFormStepActions;
};

export function AgentFormStepBindingsSection({ form, setForm, kbs, allAgents, a2aPeers, agent, actions }: Props) {
  const { roleOptions, invokePolicies, toggleKb, toggleSubAgent, setSubRole, toggleA2aPeer, setA2aKeywords } = actions;
  const otherAgents = allAgents.filter((a) => a.id !== agent?.id);

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <div className="rounded-lg border border-line-soft p-4">
        <p className="mb-2 text-xs font-medium text-ink-muted">知识库（可多选）</p>
        <div className="flex max-h-40 flex-wrap gap-2 overflow-y-auto">
          {kbs.length === 0 && <span className="text-xs text-ink-faint">暂无知识库</span>}
          {kbs.map((kb) => (
            <label key={kb.id} className="flex cursor-pointer items-center gap-1 text-xs">
              <input type="checkbox" checked={form.kb_ids.includes(kb.id)} onChange={() => toggleKb(kb.id)} />
              {kb.name}
            </label>
          ))}
        </div>
      </div>
      <div className="rounded-lg border border-brand/30 bg-brand-light/30 p-4">
        <p className="mb-1 text-xs font-medium text-ink">内部协同（可选，最多 8 个）</p>
        <p className="mb-2 text-xs text-ink-muted">绑定同租户其他智能体，由 DeepAgents 做平台内委派；非 A2A 外部协议。</p>
        <div className="max-h-48 space-y-2 overflow-y-auto">
          {otherAgents.map((a) => {
            const bound = form.sub_agents.find((s) => s.child_agent_id === a.id);
            return (
              <div key={a.id} className="flex flex-wrap items-center gap-2 rounded border border-line-soft bg-surface px-2 py-1.5">
                <label className="flex cursor-pointer items-center gap-1 text-xs">
                  <input type="checkbox" checked={Boolean(bound)} onChange={() => toggleSubAgent(a.id)} />
                  {a.name}
                </label>
                {bound && (
                  <select className="input-field py-0.5 text-xs" value={bound.role_hint ?? ""} onChange={(e) => setSubRole(a.id, e.target.value)}>
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
          {otherAgents.length === 0 && <span className="text-xs text-ink-faint">暂无其他智能体可绑定</span>}
        </div>
      </div>
      {form.sub_agents.length > 0 && form.kb_ids.length > 0 && (
        <p className="text-xs text-ink-muted lg:col-span-2">已启用内部协同：对话走 DeepAgents 规划，RAG LangGraph 不生效。</p>
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
          {a2aPeers.length === 0 && <span className="text-xs text-ink-faint">请先在智能体列表 A2A Tab 登记外部 Agent 并同步 Card。</span>}
          {a2aPeers.map((p) => {
            const bound = form.a2a_peers.find((x) => x.peer_id === p.id);
            return (
              <div key={p.id} className="rounded border border-line-soft bg-surface px-2 py-2 text-xs">
                <label className="flex cursor-pointer items-center gap-2">
                  <input type="checkbox" checked={Boolean(bound)} onChange={() => toggleA2aPeer(p.id)} />
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
}
