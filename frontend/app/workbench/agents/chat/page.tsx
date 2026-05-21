"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { agentModeLabel, buildCreateAgentPayload } from "@/lib/agent-utils";
import type { Flow, KnowledgeBase, ModelConfig, PromptTemplate } from "@/lib/types";

export default function AgentsChatPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[calc(100vh-3.5rem)] items-center justify-center text-ink-muted">
          加载对话工作台…
        </div>
      }
    >
      <AgentsChatContent />
    </Suspense>
  );
}

function AgentsChatContent() {
  const searchParams = useSearchParams();
  const agentFromUrl = searchParams.get("agent");
  const { ready } = useRequireAuth();
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [flows, setFlows] = useState<Flow[]>([]);
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>(agentFromUrl ?? "");
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [steps, setSteps] = useState<Record<string, unknown>[]>([]);
  const [conversationId, setConversationId] = useState(() => crypto.randomUUID());
  const [chatting, setChatting] = useState(false);

  const list = usePagedList(useCallback((p, s) => api.listAgents(p, s), []), { enabled: ready });

  useEffect(() => {
    if (!ready) return;
    Promise.all([
      api.listKbs(1),
      api.listFlows(1),
      api.listPromptTemplates(1),
      api.listModelConfigs(),
    ]).then(([k, f, p, m]) => {
      setKbs(k.items);
      setFlows(f.items.filter((x) => x.status === "published"));
      setPrompts(p.items);
      setModels(m);
    });
  }, [ready]);

  useEffect(() => {
    if (agentFromUrl) setSelectedAgent(agentFromUrl);
  }, [agentFromUrl]);

  useEffect(() => {
    if (selectedAgent) return;
    if (list.items[0]) setSelectedAgent(list.items[0].id);
  }, [list.items, selectedAgent]);

  const selected = list.items.find((a) => a.id === selectedAgent);

  const createAgent = async () => {
    const agent = await api.createAgent(
      buildCreateAgentPayload(list.total, { flows, prompts, models }),
    );
    await list.reload();
    setSelectedAgent(agent.id);
  };

  const chat = async () => {
    if (!selectedAgent || !query.trim()) return;
    setChatting(true);
    setAnswer("");
    setSteps([]);
    try {
      const res = await api.chatAgent(selectedAgent, query.trim(), { conversationId });
      setAnswer(res.answer);
      setSteps(res.steps ?? []);
    } catch (e) {
      setAnswer(e instanceof Error ? e.message : "对话失败");
    } finally {
      setChatting(false);
    }
  };

  if (!ready || list.loading) {
    return (
      <div className="flex h-[calc(100vh-3.5rem)] items-center justify-center text-ink-muted">
        加载对话工作台…
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      <aside className="flex w-72 shrink-0 flex-col border-r border-line bg-surface">
        <div className="flex items-center justify-between border-b border-line-soft px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold text-ink">智能体</h2>
            <p className="text-xs text-ink-faint">共 {list.total} 个</p>
          </div>
          <button type="button" onClick={createAgent} className="btn-ghost text-brand">
            + 新建
          </button>
        </div>
        <ul className="flex-1 overflow-y-auto p-2">
          {list.items.map((a) => (
            <li key={a.id}>
              <button
                type="button"
                onClick={() => setSelectedAgent(a.id)}
                className={`mb-1 w-full rounded-lg border px-3 py-2.5 text-left text-sm transition ${
                  selectedAgent === a.id
                    ? "border-brand/30 bg-brand-light"
                    : "border-transparent hover:border-line hover:bg-surface-muted"
                }`}
              >
                <p className="font-medium text-ink">{a.name}</p>
                <p className="mt-0.5 text-xs text-ink-muted">{agentModeLabel(a)}</p>
              </button>
            </li>
          ))}
        </ul>
        <div className="border-t border-line-soft p-2">
          <ResourceListFooter
            page={list.page}
            size={list.size}
            total={list.total}
            onPageChange={list.setPage}
          />
        </div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col bg-surface-subtle">
        <div className="flex items-start justify-between gap-4 border-b border-line bg-surface px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold text-ink">{selected?.name ?? "选择智能体"}</h2>
            <p className="mt-0.5 text-sm text-ink-muted">在此与智能体对话，结果经合规检测后返回</p>
          </div>
          <button
            type="button"
            className="btn-ghost shrink-0 text-xs"
            onClick={() => {
              setConversationId(crypto.randomUUID());
              setAnswer("");
              setSteps([]);
            }}
          >
            新会话
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {answer ? (
            <div className="max-w-3xl space-y-3">
              {steps.length > 0 && (
                <details className="card p-3 text-xs text-ink-muted">
                  <summary className="cursor-pointer font-medium text-ink">
                    执行步骤（{steps.length}）
                  </summary>
                  <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap font-mono text-[11px]">
                    {JSON.stringify(steps, null, 2)}
                  </pre>
                </details>
              )}
              <div className="card p-4">
                <p className="mb-2 text-xs font-medium text-brand">助手</p>
                <div className="whitespace-pre-wrap text-sm leading-relaxed text-ink">{answer}</div>
              </div>
            </div>
          ) : (
            <div className="flex h-full min-h-[200px] flex-col items-center justify-center text-center">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-light">
                <span className="text-2xl text-brand">◇</span>
              </div>
              <p className="text-sm text-ink-muted">输入问题开始对话</p>
              <p className="mt-1 text-xs text-ink-faint">
                支持直连、RAG、流程；绑定子智能体时由规划器协同回答
              </p>
            </div>
          )}
        </div>

        <div className="border-t border-line bg-surface p-4">
          <div className="mx-auto flex max-w-3xl gap-2">
            <textarea
              className="input-field min-h-[44px] flex-1 resize-none py-2.5"
              rows={2}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  chat();
                }
              }}
              placeholder="输入问题，Enter 发送，Shift+Enter 换行"
            />
            <button
              type="button"
              onClick={chat}
              disabled={chatting || !selectedAgent}
              className="btn-primary shrink-0 self-end px-6"
            >
              {chatting ? "思考中…" : "发送"}
            </button>
          </div>
        </div>
      </section>

      <aside className="hidden w-52 shrink-0 border-l border-line bg-surface p-4 xl:block">
        <p className="text-xs font-semibold uppercase tracking-wider text-ink-faint">资源概览</p>
        <dl className="mt-4 space-y-3 text-sm">
          <div>
            <dt className="text-ink-faint">知识库</dt>
            <dd className="font-medium text-ink">{kbs.length}</dd>
          </div>
          <div>
            <dt className="text-ink-faint">已发布流程</dt>
            <dd className="font-medium text-ink">{flows.length}</dd>
          </div>
          <div>
            <dt className="text-ink-faint">提示词模版</dt>
            <dd className="font-medium text-ink">{prompts.length}</dd>
          </div>
          <div>
            <dt className="text-ink-faint">模型配置</dt>
            <dd className="font-medium text-ink">{models.length}</dd>
          </div>
        </dl>
        <div className="mt-6 rounded-lg bg-brand-light p-3 text-xs leading-relaxed text-ink-muted">
          从左侧切换智能体；可按需绑定知识库或流程以增强能力。
        </div>
      </aside>
    </div>
  );
}
