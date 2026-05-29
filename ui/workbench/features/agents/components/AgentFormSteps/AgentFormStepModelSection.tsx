"use client";

import { agentFormStepWidth, type AgentFormStepContentProps } from "@/components/agent/agent-form-step-types";

type Props = Pick<AgentFormStepContentProps, "form" | "setForm" | "models" | "prompts" | "designMode">;

export function AgentFormStepModelSection({ form, setForm, models, prompts, designMode }: Props) {
  return (
    <div className={`mx-auto ${agentFormStepWidth(designMode)} space-y-5`}>
      <label className="block text-sm">
        <span className="mb-1 block text-ink-muted">大模型</span>
        <select className="input-field w-full" value={form.model_config_id} onChange={(e) => setForm((f) => ({ ...f, model_config_id: e.target.value }))}>
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
        <select className="input-field w-full" value={form.prompt_template_id} onChange={(e) => setForm((f) => ({ ...f, prompt_template_id: e.target.value }))}>
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
      <label className="flex cursor-pointer items-start gap-2 text-sm">
        <input
          type="checkbox"
          className="mt-1"
          checked={form.carry_forward_media}
          onChange={(e) => setForm((f) => ({ ...f, carry_forward_media: e.target.checked }))}
        />
        <span>
          <span className="font-medium text-ink">多轮识图沿用附图</span>
          <span className="mt-0.5 block text-xs text-ink-muted">用户未上传新图时，自动带上一条用户消息中的图片（最多 4 张，与每轮上限一致）</span>
        </span>
      </label>
    </div>
  );
}
