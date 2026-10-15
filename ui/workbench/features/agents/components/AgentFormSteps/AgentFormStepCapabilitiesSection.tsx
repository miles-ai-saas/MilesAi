"use client";

import type { ReactNode } from "react";
import type { AgentFormStepActions } from "@/features/agents/hooks/use-agent-form-step-actions";
import { agentFormStepWidth, type AgentFormStepContentProps } from "@/features/agents/components/AgentFormStepContent";
import { MultiSelectDropdown } from "@/components/ui/MultiSelectDropdown";

type Props = Pick<
  AgentFormStepContentProps,
  "form" | "setForm" | "flows" | "skills" | "mcps" | "toolCatalog" | "onOpenFlowCanvas" | "designMode"
> & {
  actions: AgentFormStepActions;
};

function SectionCard({
  title,
  hint,
  count,
  accent,
  children,
}: {
  title: string;
  hint?: string;
  count?: number;
  accent?: boolean;
  children: ReactNode;
}) {
  return (
    <section
      className={
        accent
          ? "rounded-xl border border-brand/25 bg-brand-light/25 p-4"
          : "rounded-xl border border-line-soft bg-surface p-4"
      }
    >
      <header className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="text-sm font-medium text-ink">{title}</h4>
          {hint ? <p className="mt-0.5 text-xs leading-relaxed text-ink-muted">{hint}</p> : null}
        </div>
        {typeof count === "number" ? (
          <span className="shrink-0 rounded-md bg-surface-muted px-2 py-0.5 text-[11px] tabular-nums text-ink-muted">
            已选 {count}
          </span>
        ) : null}
      </header>
      {children}
    </section>
  );
}

function SelectChip({
  selected,
  label,
  detail,
  onToggle,
  disabled,
}: {
  selected: boolean;
  label: string;
  detail?: string;
  onToggle: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onToggle}
      aria-pressed={selected}
      className={
        selected
          ? "rounded-lg border border-brand bg-brand-light/50 px-2.5 py-1.5 text-left text-xs font-medium text-ink transition disabled:cursor-not-allowed disabled:opacity-45"
          : "rounded-lg border border-line-soft bg-surface px-2.5 py-1.5 text-left text-xs text-ink-muted transition hover:border-line hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-45"
      }
    >
      <span className="block">{label}</span>
      {detail ? <span className="mt-0.5 block text-[11px] font-normal text-ink-faint">{detail}</span> : null}
    </button>
  );
}

function ToggleRow({
  checked,
  disabled,
  title,
  description,
  onChange,
}: {
  checked: boolean;
  disabled?: boolean;
  title: string;
  description: string;
  onChange: (next: boolean) => void;
}) {
  return (
    <label className={`flex gap-3 ${disabled ? "cursor-not-allowed opacity-55" : "cursor-pointer"}`}>
      <input
        type="checkbox"
        className="mt-1 rounded border-line text-brand"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="min-w-0">
        <span className="block text-sm font-medium text-ink">{title}</span>
        <span className="mt-0.5 block text-xs leading-relaxed text-ink-muted">{description}</span>
      </span>
    </label>
  );
}

export function AgentFormStepCapabilitiesSection({
  form,
  setForm,
  flows,
  skills,
  mcps,
  toolCatalog,
  onOpenFlowCanvas,
  designMode,
  actions,
}: Props) {
  const { imageGenModels, videoGenModels, toggleToolSlug } = actions;

  return (
    <div className={`mx-auto ${agentFormStepWidth(designMode)} space-y-4`}>
      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard
          title="编排流程"
          hint="绑定已发布画布后，对话经 LangGraph 执行（并行 / 条件分支）。留空则走直连、RAG 或子智能体。"
        >
          <div className="flex gap-2">
            <select
              className="input-field min-w-0 flex-1"
              value={form.published_flow_id}
              onChange={(e) => setForm((f) => ({ ...f, published_flow_id: e.target.value }))}
            >
              <option value="">无流程（直连 / RAG / 子智能体）</option>
              {flows.map((fl) => (
                <option key={fl.id} value={fl.id}>
                  {fl.name}
                </option>
              ))}
            </select>
            {form.published_flow_id && onOpenFlowCanvas ? (
              <button type="button" className="btn-ghost shrink-0 border border-line" onClick={onOpenFlowCanvas}>
                画布
              </button>
            ) : null}
          </div>
          {form.published_flow_id && form.sub_agents.length === 0 ? (
            <p className="mt-2 text-xs text-brand">已绑定流程：本轮对话将优先走画布执行。</p>
          ) : null}
        </SectionCard>

        <SectionCard
          title="技能包"
          count={form.skill_ids.length}
          hint="模型可通过 skill_read_reference / skill_run_script 读取手册与执行脚本；多选时按 slug 指定。"
        >
          <MultiSelectDropdown
            options={skills.map((s) => ({ value: s.id, label: s.name }))}
            value={form.skill_ids}
            onChange={(skill_ids) => setForm((f) => ({ ...f, skill_ids }))}
            placeholder="选择技能包"
            emptyText="暂无技能包"
            panelTitle="技能包（可多选）"
          />
        </SectionCard>
      </div>

      <SectionCard
        title="平台工具"
        accent
        count={form.enable_tool_calling ? form.tool_slugs.length : undefined}
        hint="与 MCP 独立。基线内置（计算器 / HTTP / 时间 / 知识库检索）与自定义 HTTP 始终可用；外呼与执行类须勾选后才进入 function schema。"
      >
        <div className="space-y-4">
          <ToggleRow
            checked={form.enable_tool_calling}
            title="启用平台工具自动调用"
            description="开启 function calling；绑定知识库时 knowledge_search 自动可用。"
            onChange={(checked) =>
              setForm((f) => ({
                ...f,
                enable_tool_calling: checked,
                tool_slugs: checked ? f.tool_slugs : [],
                enable_generative_tools: checked ? f.enable_generative_tools : false,
              }))
            }
          />

          <div className="border-t border-brand/15 pt-4">
            <ToggleRow
              checked={form.enable_generative_tools}
              disabled={!form.enable_tool_calling}
              title="启用生图 / 生视频工具"
              description="对话可调用 generate_image、generate_video；有知识库时须同时开启平台工具。"
              onChange={(checked) =>
                setForm((f) => ({
                  ...f,
                  enable_generative_tools: checked,
                  enable_tool_calling: checked ? true : f.enable_tool_calling,
                }))
              }
            />
            {form.enable_generative_tools && form.enable_tool_calling ? (
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <label className="block text-xs">
                  <span className="mb-1 block text-ink-muted">生图模型（可选）</span>
                  <select
                    className="input-field w-full text-sm"
                    value={form.generative_image_model_id}
                    onChange={(e) => setForm((f) => ({ ...f, generative_image_model_id: e.target.value }))}
                  >
                    <option value="">默认（租户 image_gen）</option>
                    {imageGenModels.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name}
                        {!m.has_api_key ? "（缺 Key）" : ""}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-xs">
                  <span className="mb-1 block text-ink-muted">生视频模型（可选）</span>
                  <select
                    className="input-field w-full text-sm"
                    value={form.generative_video_model_id}
                    onChange={(e) => setForm((f) => ({ ...f, generative_video_model_id: e.target.value }))}
                  >
                    <option value="">默认（租户 video_gen）</option>
                    {videoGenModels.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name}
                        {!m.has_api_key ? "（缺 Key）" : ""}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            ) : null}
          </div>

          {form.enable_tool_calling ? (
            <div className="border-t border-brand/15 pt-4">
              <p className="mb-2 text-xs font-medium text-ink-muted">可选工具（点击切换）</p>
              {toolCatalog.length === 0 ? (
                <p className="text-xs text-ink-faint">暂无平台工具，请先在工具页创建</p>
              ) : (
                <div className="flex max-h-44 flex-wrap gap-2 overflow-y-auto">
                  {toolCatalog.map((t) => (
                    <SelectChip
                      key={`${t.source}-${t.slug}`}
                      selected={form.tool_slugs.includes(t.slug)}
                      label={t.name}
                      detail={t.slug}
                      onToggle={() => toggleToolSlug(t.slug)}
                    />
                  ))}
                </div>
              )}
            </div>
          ) : null}
        </div>
      </SectionCard>

      <SectionCard
        title="MCP 服务"
        count={form.mcp_service_ids.length}
        hint="与平台工具分离；绑定并同步后，其工具加入可调用集合（只读免确认，其余需用户确认）。"
      >
        <MultiSelectDropdown
          options={mcps.map((m) => ({
            value: m.id,
            label: m.name,
            detail: `${m.tools_cache?.length ?? 0} 个工具`,
          }))}
          value={form.mcp_service_ids}
          onChange={(mcp_service_ids) => setForm((f) => ({ ...f, mcp_service_ids }))}
          placeholder="选择 MCP 服务"
          emptyText="暂无 MCP 服务"
          panelTitle="MCP 服务（可多选）"
        />
      </SectionCard>

      <SectionCard title="对外发布" hint="仅 custom 且启用的智能体生效；Card 公开发现，调用须带该智能体的 X-API-Key。">
        <ToggleRow
          checked={form.a2a_publish}
          title="发布为 A2A Server"
          description="外部客户端可拉取 Agent Card 并调用 message/send。发现地址：/api/v1/open/a2a/agents/{agent_id}/.well-known/agent-card.json"
          onChange={(checked) => setForm((f) => ({ ...f, a2a_publish: checked }))}
        />
      </SectionCard>
    </div>
  );
}
