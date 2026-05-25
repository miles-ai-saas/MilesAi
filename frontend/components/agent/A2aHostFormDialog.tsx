"use client";

import { useEffect, useState } from "react";
import {
  AGENT_HOST_FORM_STEPS,
  agentToHostFormValues,
  buildHostAgentConfig,
  emptyHostAgentForm,
  type A2aHostFormValues,
} from "@/components/agent/a2a-host-form-shared";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { api } from "@/lib/api";
import type { Agent, A2aPeer, ModelConfig, PromptTemplate } from "@/lib/types";

type Props = {
  open: boolean;
  title: string;
  agent?: Agent | null;
  onClose: () => void;
  onSaved: () => void;
};

export function A2aHostFormDialog({ open, title, agent, onClose, onSaved }: Props) {
  const [form, setForm] = useState<A2aHostFormValues>(emptyHostAgentForm());
  const [step, setStep] = useState(0);
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [a2aPeers, setA2aPeers] = useState<A2aPeer[]>([]);
  const [busy, setBusy] = useState(false);

  const isLastStep = step === AGENT_HOST_FORM_STEPS.length - 1;
  const canNext = step === 0 ? form.name.trim().length > 0 : step === 1 ? Boolean(form.model_config_id) : true;

  useEffect(() => {
    if (!open) return;
    setStep(0);
    Promise.all([
      api.listPromptTemplates(1, 100),
      api.listModelConfigs(),
      api.listA2aPeers(1, 100),
    ]).then(([promptRes, modelRes, a2aRes]) => {
      setPrompts(promptRes.items);
      setModels(modelRes);
      setA2aPeers(a2aRes.items.filter((p) => p.status === "active"));
    });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (agent) setForm(agentToHostFormValues(agent));
    else setForm(emptyHostAgentForm());
  }, [open, agent]);

  const togglePeer = (peerId: string) => {
    setForm((f) => {
      const exists = f.a2a_peers.find((p) => p.peer_id === peerId);
      if (exists) {
        return { ...f, a2a_peers: f.a2a_peers.filter((p) => p.peer_id !== peerId) };
      }
      if (f.a2a_peers.length >= 8) return f;
      return {
        ...f,
        a2a_peers: [...f.a2a_peers, { peer_id: peerId, trigger_keywords: [], enabled: true }],
      };
    });
  };

  const setKeywords = (peerId: string, raw: string) => {
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

  const onSubmit = async () => {
    if (!form.name.trim() || !form.model_config_id || form.a2a_peers.length < 1) return;
    setBusy(true);
    try {
      const payload = {
        agent_type: "a2a" as const,
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        system_prompt: form.system_prompt.trim() || undefined,
        model_config_id: form.model_config_id,
        prompt_template_id: form.prompt_template_id || undefined,
        a2a_peers: form.a2a_peers,
        kb_ids: [] as string[],
        sub_agents: [],
        config: buildHostAgentConfig(form, (agent?.config as Record<string, unknown>) ?? {}),
      };
      if (agent) {
        await api.updateAgent(agent.id, payload);
      } else {
        await api.createAgent(payload);
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
    else setStep((s) => Math.min(s + 1, AGENT_HOST_FORM_STEPS.length - 1));
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
              disabled={busy || !canNext || (isLastStep && form.a2a_peers.length < 1)}
              onClick={goNext}
            >
              {busy ? "保存中…" : isLastStep ? (agent ? "保存" : "创建") : "下一步"}
            </button>
          </div>
          <button type="button" className="btn-ghost" onClick={onClose}>
            取消
          </button>
        </div>
      }
    >
      <div className="mx-auto max-w-2xl space-y-6 py-4">
        <p className="text-xs text-ink-muted">
          步骤 {step + 1}/{AGENT_HOST_FORM_STEPS.length} · {AGENT_HOST_FORM_STEPS[step].title}
        </p>
        {step === 0 && (
          <div className="space-y-4">
            <label className="block text-sm">
              <span className="mb-1 block text-ink-muted">宿主名称</span>
              <input
                className="input-field w-full"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="例如：跨厂商协同入口"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-ink-muted">描述</span>
              <textarea
                className="input-field w-full resize-none"
                rows={3}
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              />
            </label>
          </div>
        )}
        {step === 1 && (
          <div className="space-y-4">
            <label className="block text-sm">
              <span className="mb-1 block text-ink-muted">编排模型（必填）</span>
              <select
                className="input-field w-full"
                value={form.model_config_id}
                onChange={(e) => setForm((f) => ({ ...f, model_config_id: e.target.value }))}
              >
                <option value="">请选择</option>
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
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
                <option value="">无</option>
                {prompts.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-ink-muted">编排提示词</span>
              <textarea
                className="input-field min-h-[120px] w-full resize-none"
                value={form.system_prompt}
                onChange={(e) => setForm((f) => ({ ...f, system_prompt: e.target.value }))}
                placeholder="说明如何拆解任务、选择外部 Agent、汇总结果…"
              />
            </label>
          </div>
        )}
        {step === 2 && (
          <div className="space-y-4">
            <label className="block text-sm">
              <span className="mb-1 block text-ink-muted">外部调用策略</span>
              <select
                className="input-field w-full"
                value={form.a2a_invoke_policy}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    a2a_invoke_policy: e.target.value as typeof f.a2a_invoke_policy,
                  }))
                }
              >
                <option value="rules_then_plan">规则优先，未命中则自动规划</option>
                <option value="rules_only">仅规则触发</option>
                <option value="plan_only">仅自动规划</option>
              </select>
            </label>
            <p className="text-xs text-ink-muted">
              至少选择 1 个已在「外部登记」中同步 Card 的 Agent。规则关键词命中则必调该成员。
            </p>
            <div className="max-h-64 space-y-2 overflow-y-auto">
              {a2aPeers.length === 0 && (
                <p className="text-xs text-ink-faint">请先在 A2A Tab → 外部登记 中添加并同步 Card。</p>
              )}
              {a2aPeers.map((p) => {
                const bound = form.a2a_peers.find((x) => x.peer_id === p.id);
                return (
                  <div key={p.id} className="rounded-lg border border-line-soft p-3 text-xs">
                    <label className="flex cursor-pointer items-center gap-2">
                      <input
                        type="checkbox"
                        checked={Boolean(bound)}
                        onChange={() => togglePeer(p.id)}
                      />
                      <span className="font-medium text-ink">{p.name}</span>
                      <span className="text-ink-faint">{p.card_display_name ?? "已连通"}</span>
                    </label>
                    {bound && (
                      <input
                        className="input-field mt-2 w-full py-1"
                        placeholder="规则关键词，逗号分隔"
                        value={(bound.trigger_keywords ?? []).join(", ")}
                        onChange={(e) => setKeywords(p.id, e.target.value)}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </ResourceDialog>
  );
}
