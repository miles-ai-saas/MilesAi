"use client";

import type { A2aHostFormDialogVm } from "@/features/agents/hooks/use-a2a-host-form-dialog";
import type { A2aHostFormValues } from "@/features/agents/components/a2a-host-form-shared";
import type { EnumOption } from "@/lib/enum-meta";
import type { A2aPeer, ModelConfig, PromptTemplate } from "@/lib/types";

export function A2aHostFormBasicStep({ form, setForm }: { form: A2aHostFormValues; setForm: A2aHostFormDialogVm["setForm"] }) {
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

export function A2aHostFormModelStep({
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
  return (
    <div className="space-y-4">
      <label className="block text-sm">
        <span className="mb-1 block text-ink-muted">编排模型（必填）</span>
        <select className="input-field w-full" value={form.model_config_id} onChange={(e) => setForm((f) => ({ ...f, model_config_id: e.target.value }))}>
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

export function A2aHostFormPeersStep({
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
