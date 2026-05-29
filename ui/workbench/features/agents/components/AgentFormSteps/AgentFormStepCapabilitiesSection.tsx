"use client";

import type { AgentFormStepActions } from "@/features/agents/hooks/use-agent-form-step-actions";
import type { AgentFormStepContentProps } from "@/features/agents/components/agent-form-step-types";

type Props = Pick<
  AgentFormStepContentProps,
  "form" | "setForm" | "flows" | "skills" | "mcps" | "toolCatalog" | "onOpenFlowCanvas"
> & {
  actions: AgentFormStepActions;
};

export function AgentFormStepCapabilitiesSection({ form, setForm, flows, skills, mcps, toolCatalog, onOpenFlowCanvas, actions }: Props) {
  const { imageGenModels, videoGenModels, toggleMcp, toggleToolSlug } = actions;

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <label className="block text-sm lg:col-span-2">
        <span className="mb-1 block text-ink-muted">技能包</span>
        <select className="input-field w-full" value={form.skill_package_id} onChange={(e) => setForm((f) => ({ ...f, skill_package_id: e.target.value }))}>
          <option value="">无技能包</option>
          {skills.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </label>
      <label className="block text-sm">
        <span className="mb-1 block text-ink-muted">已发布编排流程</span>
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
          {form.published_flow_id && onOpenFlowCanvas && (
            <button type="button" className="btn-ghost shrink-0 border border-line" onClick={onOpenFlowCanvas}>
              画布
            </button>
          )}
        </div>
      </label>
      {form.published_flow_id && form.sub_agents.length === 0 && (
        <p className="text-xs text-ink-muted lg:col-span-2">已绑定流程：对话将经 LangGraph 编译执行画布（并行 / 条件分支）。</p>
      )}
      <div className="rounded-lg border border-brand/30 bg-brand-light/20 p-4 lg:col-span-2">
        <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-ink">
          <input
            type="checkbox"
            checked={form.enable_tool_calling}
            onChange={(e) =>
              setForm((f) => ({
                ...f,
                enable_tool_calling: e.target.checked,
                tool_slugs: e.target.checked ? f.tool_slugs : [],
                enable_generative_tools: e.target.checked ? f.enable_generative_tools : false,
              }))
            }
          />
          启用平台工具自动调用（function calling）
        </label>
        <p className="mt-1 text-xs text-ink-muted">与 MCP 独立。未勾选下方工具则允许全部内置 + 自定义 HTTP。生图/生视频亦依赖本项。</p>
        <label className="mt-3 flex cursor-pointer items-center gap-2 text-sm text-ink">
          <input
            type="checkbox"
            checked={form.enable_generative_tools}
            disabled={!form.enable_tool_calling}
            onChange={(e) =>
              setForm((f) => ({
                ...f,
                enable_generative_tools: e.target.checked,
                enable_tool_calling: e.target.checked ? true : f.enable_tool_calling,
              }))
            }
          />
          启用生图 / 生视频工具（万相优先）
        </label>
        <p className="mt-1 text-xs text-ink-muted">
          对话中可调用 generate_image、generate_video；产出出现在回复与「生成素材」。有知识库时须同时开启「平台工具」：将走 knowledge_search +
          生成工具，不再使用自动 LangGraph RAG。
        </p>
        {form.enable_generative_tools && form.enable_tool_calling && (
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
        )}
        {form.enable_tool_calling && (
          <div className="mt-3 flex max-h-36 flex-wrap gap-2 overflow-y-auto">
            {toolCatalog.length === 0 && <span className="text-xs text-ink-faint">暂无平台工具，请先在工具页创建</span>}
            {toolCatalog.map((t) => (
              <label key={`${t.source}-${t.slug}`} className="flex cursor-pointer items-center gap-1 text-xs">
                <input type="checkbox" checked={form.tool_slugs.includes(t.slug)} onChange={() => toggleToolSlug(t.slug)} />
                {t.name} ({t.slug})
              </label>
            ))}
          </div>
        )}
      </div>
      <div className="rounded-lg border border-line-soft p-4 lg:col-span-2">
        <p className="mb-1 text-xs font-medium text-ink-muted">MCP 服务（可多选，仅注入提示词）</p>
        <p className="mb-2 text-xs text-ink-faint">MCP 与平台工具分离；绑定后写入系统提示，对话内暂不自动调用。</p>
        <div className="flex max-h-32 flex-wrap gap-2 overflow-y-auto">
          {mcps.length === 0 && <span className="text-xs text-ink-faint">暂无 MCP 服务</span>}
          {mcps.map((m) => (
            <label key={m.id} className="flex cursor-pointer items-center gap-1 text-xs">
              <input type="checkbox" checked={form.mcp_service_ids.includes(m.id)} onChange={() => toggleMcp(m.id)} />
              {m.name} ({m.tools_cache?.length ?? 0})
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}
