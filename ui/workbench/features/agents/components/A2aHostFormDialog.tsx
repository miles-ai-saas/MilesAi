"use client";

/** A2A 互联宿主表单（链路 §4 `useA2aMeta`）。 */

import { useMemo } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import type { A2aHostFormValues, A2aHostFormDialogVm } from "@/features/agents/hooks/use-a2a-host-form-dialog";
import { useA2aHostFormDialog } from "@/features/agents/hooks/use-a2a-host-form-dialog";
import { CHAT_MODEL_TYPES } from "@/features/models/lib/model-labels";
import type { EnumOption } from "@/lib/enum-meta";
import type { Agent, A2aPeer, ModelConfig, PromptTemplate } from "@/lib/types";

type Props = {
  open: boolean;
  title: string;
  agent?: Agent | null;
  onClose: () => void;
  onSaved: () => void;
};

function A2aHostFormBasicStep({ form, setForm }: { form: A2aHostFormValues; setForm: A2aHostFormDialogVm["setForm"] }) {
  return (
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
  );
}

function A2aHostFormModelStep({
  form,
  setForm,
  models,
  prompts,
}: {
  form: A2aHostFormValues;
  setForm: A2aHostFormDialogVm["setForm"];
  models: ModelConfig[];
  prompts: PromptTemplate[];
}) {
  const chatModels = useMemo(() => {
    const filtered = models.filter((m) => m.is_active !== false && CHAT_MODEL_TYPES.has(m.model_type));
    if (form.model_config_id) {
      const selected = models.find((m) => m.id === form.model_config_id);
      if (selected && !CHAT_MODEL_TYPES.has(selected.model_type)) {
        filtered.push(selected);
      }
    }
    return filtered;
  }, [models, form.model_config_id]);

  return (
    <div className="space-y-4">
      <label className="block text-sm">
        <span className="mb-1 block text-ink-muted">编排模型（必填）</span>
        <select className="input-field w-full" value={form.model_config_id} onChange={(e) => setForm((f) => ({ ...f, model_config_id: e.target.value }))}>
          <option value="">请选择</option>
          {chatModels.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
        <span className="mt-0.5 block text-xs text-ink-faint">仅显示对话类模型（llm / reasoning / vision）</span>
      </label>
      <label className="block text-sm">
        <span className="mb-1 block text-ink-muted">提示词模版</span>
        <select className="input-field w-full" value={form.prompt_template_id} onChange={(e) => setForm((f) => ({ ...f, prompt_template_id: e.target.value }))}>
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
  );
}

function A2aHostFormPeersStep({
  form,
  setForm,
  a2aPeers,
  invokePolicies,
  togglePeer,
  setKeywords,
}: {
  form: A2aHostFormValues;
  setForm: A2aHostFormDialogVm["setForm"];
  a2aPeers: A2aPeer[];
  invokePolicies: EnumOption[];
  togglePeer: A2aHostFormDialogVm["togglePeer"];
  setKeywords: A2aHostFormDialogVm["setKeywords"];
}) {
  return (
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
          {invokePolicies.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
      <p className="text-xs text-ink-muted">至少选择 1 个已在「外部登记」中同步 Card 的 Agent。规则关键词命中则必调该成员。</p>
      <div className="max-h-64 space-y-2 overflow-y-auto">
        {a2aPeers.length === 0 && <p className="text-xs text-ink-faint">请先在 A2A Tab → 外部登记 中添加并同步 Card。</p>}
        {a2aPeers.map((p) => {
          const bound = form.a2a_peers.find((x) => x.peer_id === p.id);
          return (
            <div key={p.id} className="rounded-lg border border-line-soft p-3 text-xs">
              <label className="flex cursor-pointer items-center gap-2">
                <input type="checkbox" checked={Boolean(bound)} onChange={() => togglePeer(p.id)} />
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
  );
}

export function A2aHostFormDialog({ open, title, agent, onClose, onSaved }: Props) {
  const vm = useA2aHostFormDialog({ open, agent, onClose, onSaved });

  return (
    <ResourceDialog
      open={open}
      title={title}
      size="sheet"
      onClose={onClose}
      footer={
        <div className="flex w-full flex-wrap items-center justify-between gap-3">
          <div className="flex gap-2">
            <button type="button" className="btn-ghost border border-line" disabled={vm.step === 0} onClick={() => vm.setStep((s) => Math.max(0, s - 1))}>
              上一步
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={vm.busy || !vm.canNext || (vm.isLastStep && vm.form.a2a_peers.length < 1)}
              onClick={vm.goNext}
            >
              {vm.busy ? "保存中…" : vm.isLastStep ? (agent ? "保存" : "创建") : "下一步"}
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
          步骤 {vm.step + 1}/{vm.steps.length} · {vm.steps[vm.step].title}
        </p>
        {vm.step === 0 && <A2aHostFormBasicStep form={vm.form} setForm={vm.setForm} />}
        {vm.step === 1 && <A2aHostFormModelStep form={vm.form} setForm={vm.setForm} models={vm.models} prompts={vm.prompts} />}
        {vm.step === 2 && (
          <A2aHostFormPeersStep
            form={vm.form}
            setForm={vm.setForm}
            a2aPeers={vm.a2aPeers}
            invokePolicies={vm.invokePolicies}
            togglePeer={vm.togglePeer}
            setKeywords={vm.setKeywords}
          />
        )}
      </div>
    </ResourceDialog>
  );
}
