"use client";

import { formatAgentCode } from "@/components/agent/agent-form-shared";
import { agentFormStepWidth, type AgentFormStepContentProps } from "@/components/agent/agent-form-step-types";
import { TagPicker } from "@/components/tag/TagPicker";

type Props = Pick<AgentFormStepContentProps, "form" | "setForm" | "agentId" | "categories" | "designMode">;

export function AgentFormStepBasicSection({ form, setForm, agentId, categories, designMode }: Props) {
  return (
    <div className={`mx-auto ${agentFormStepWidth(designMode)} space-y-5`}>
      <label className="block text-sm">
        <span className="mb-1 block text-ink-muted">分类</span>
        <select className="input-field w-full" value={form.category_id} onChange={(e) => setForm((f) => ({ ...f, category_id: e.target.value }))}>
          <option value="">未分类</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      <label className="block text-sm">
        <span className="mb-1 block text-ink-muted">标签</span>
        <TagPicker value={form.tag_ids} onChange={(tag_ids) => setForm((f) => ({ ...f, tag_ids }))} />
      </label>
      <label className="block text-sm">
        <span className="mb-1 block text-ink-muted">
          名称 <span className="text-brand">*</span>
        </span>
        <input
          className="input-field w-full"
          placeholder="请输入智能体名称"
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
        />
      </label>
      {agentId && (
        <label className="block text-sm">
          <span className="mb-1 flex items-center gap-1 text-ink-muted">
            智能体编号
            <span className="cursor-help text-ink-faint" title="系统根据 ID 生成的展示编号，不可修改">
              ⓘ
            </span>
          </span>
          <input className="input-field w-full bg-surface-muted text-ink-muted" readOnly value={formatAgentCode(agentId)} />
        </label>
      )}
      <label className="block text-sm">
        <span className="mb-1 block text-ink-muted">
          描述 <span className="text-brand">*</span>
        </span>
        <textarea
          className="input-field h-28 w-full"
          placeholder="请输入智能体描述"
          value={form.description}
          onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
        />
      </label>
    </div>
  );
}
