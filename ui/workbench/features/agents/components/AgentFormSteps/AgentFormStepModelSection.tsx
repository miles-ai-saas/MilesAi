"use client";

import { useMemo } from "react";
import { agentFormStepWidth, type AgentFormStepContentProps } from "@/features/agents/components/AgentFormStepContent";
import { CHAT_MODEL_TYPES } from "@/features/models/lib/model-labels";

type Props = Pick<AgentFormStepContentProps, "form" | "setForm" | "models" | "prompts" | "designMode">;

export function AgentFormStepModelSection({ form, setForm, models, prompts, designMode }: Props) {
  const chatModels = useMemo(() => {
    const filtered = models.filter((m) => m.is_active !== false && CHAT_MODEL_TYPES.has(m.model_type));
    // 兜底：已有智能体选了非对话模型时仍保留在列表中
    if (form.model_config_id) {
      const selected = models.find((m) => m.id === form.model_config_id);
      if (selected && !CHAT_MODEL_TYPES.has(selected.model_type)) {
        filtered.push(selected);
      }
    }
    return filtered;
  }, [models, form.model_config_id]);

  return (
    <div className={`mx-auto ${agentFormStepWidth(designMode)} space-y-5`}>
      <label className="block text-sm">
        <span className="mb-1 block text-ink-muted">大模型</span>
        <select className="input-field w-full" value={form.model_config_id} onChange={(e) => setForm((f) => ({ ...f, model_config_id: e.target.value }))}>
          <option value="">默认模型</option>
          {chatModels.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name} ({m.model_name})
            </option>
          ))}
        </select>
        <span className="mt-0.5 block text-xs text-ink-faint">仅显示对话类模型（llm / reasoning / vision），生图/生视频模型请在能力步骤单独配置</span>
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
          <span className="mt-0.5 block text-xs text-ink-muted">用户未上传新图时，自动带上一条用户消息中的图片（每轮上限 10 张）</span>
        </span>
      </label>
    </div>
  );
}
