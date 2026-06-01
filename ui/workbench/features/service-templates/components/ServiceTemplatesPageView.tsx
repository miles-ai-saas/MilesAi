"use client";

import { BizPageHero } from "@/features/business-dashboard/components/BizPageHero";
import type { ServiceTemplatesPageVm } from "@/features/service-templates/hooks/use-service-templates-page";

const SOURCE_LABELS: Record<string, string> = {
  tenant: "租户自定义",
  global: "系统默认",
  none: "未配置",
};

export function ServiceTemplatesPageView({ vm }: { vm: ServiceTemplatesPageVm }) {
  const {
    ready,
    items,
    loading,
    canWriteProject,
    editingLine,
    stageText,
    setStageText,
    aiConfig,
    setAiConfig,
    quickPromptText,
    setQuickPromptText,
    flowTemplates,
    flowTemplatesLoading,
    saving,
    startEdit,
    cancelEdit,
    saveEdit,
    resetTemplate,
  } = vm;

  if (!ready || loading) {
    return <p className="text-sm text-ink-muted">加载中…</p>;
  }

  return (
    <div className="w-full">
      <BizPageHero
        flowStep="projects"
        compact
        title="服务线模板"
        subtitle="配置八条服务线的阶段流水线与 AI 推荐，新建工作包时自动继承"
      />

      <div className="space-y-3">
        {items.map((row) => {
          const editing = editingLine === row.service_line;
          const ai = row.ai_config ?? {};
          const hasAi =
            Boolean(ai.agent_tag) ||
            Boolean(ai.flow_template_id) ||
            Boolean(ai.chat_hint) ||
            (ai.quick_prompts?.length ?? 0) > 0;
          const flowLabel = flowTemplates.find((t) => t.id === ai.flow_template_id)?.label;

          return (
            <div key={row.service_line} className="card p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold text-ink">{row.label}</h2>
                  <p className="mt-1 text-xs text-ink-muted">
                    {row.service_line} · {SOURCE_LABELS[row.source] ?? row.source}
                    {row.source === "tenant" ? " · 已覆盖系统默认" : ""}
                  </p>
                </div>
                {canWriteProject && !editing && (
                  <div className="flex gap-2">
                    <button type="button" className="text-xs text-brand hover:underline" onClick={() => startEdit(row)}>
                      编辑
                    </button>
                    {row.source === "tenant" && (
                      <button type="button" className="text-xs text-ink-muted hover:underline" onClick={() => void resetTemplate(row.service_line)}>
                        恢复默认
                      </button>
                    )}
                  </div>
                )}
              </div>

              {editing ? (
                <div className="mt-3 space-y-4">
                  <label className="block">
                    <span className="text-xs text-ink-muted">阶段名称（每行一个）</span>
                    <textarea
                      className="input-field mt-1 w-full font-mono text-sm"
                      rows={Math.max(4, stageText.split("\n").length + 1)}
                      value={stageText}
                      onChange={(e) => setStageText(e.target.value)}
                    />
                  </label>

                  <fieldset className="space-y-3 rounded-lg border border-line-soft p-3">
                    <legend className="px-1 text-xs font-medium text-ink">AI 推荐配置</legend>
                    <label className="block">
                      <span className="text-xs text-ink-muted">智能体标签（agent_tag）</span>
                      <input
                        className="input-field mt-1 w-full text-sm"
                        placeholder="如 brand-strategy"
                        value={aiConfig.agent_tag ?? ""}
                        onChange={(e) => setAiConfig((c) => ({ ...c, agent_tag: e.target.value }))}
                      />
                    </label>
                    <label className="block">
                      <span className="text-xs text-ink-muted">流程模板</span>
                      <select
                        className="input-field mt-1 w-full text-sm"
                        value={aiConfig.flow_template_id ?? ""}
                        disabled={flowTemplatesLoading}
                        onChange={(e) => setAiConfig((c) => ({ ...c, flow_template_id: e.target.value }))}
                      >
                        <option value="">（不指定）</option>
                        {flowTemplates.map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="block">
                      <span className="text-xs text-ink-muted">对话提示（chat_hint）</span>
                      <textarea
                        className="input-field mt-1 w-full text-sm"
                        rows={2}
                        placeholder="打开 AI 对话时展示的引导语"
                        value={aiConfig.chat_hint ?? ""}
                        onChange={(e) => setAiConfig((c) => ({ ...c, chat_hint: e.target.value }))}
                      />
                    </label>
                    <label className="block">
                      <span className="text-xs text-ink-muted">快捷提示词（每行一个）</span>
                      <textarea
                        className="input-field mt-1 w-full font-mono text-sm"
                        rows={3}
                        placeholder={"帮我梳理品牌定位\n生成竞品分析大纲"}
                        value={quickPromptText}
                        onChange={(e) => setQuickPromptText(e.target.value)}
                      />
                    </label>
                  </fieldset>

                  <div className="flex gap-2">
                    <button type="button" className="btn-primary text-sm" disabled={saving} onClick={() => void saveEdit()}>
                      {saving ? "保存中…" : "保存"}
                    </button>
                    <button type="button" className="btn-ghost text-sm" onClick={cancelEdit}>取消</button>
                  </div>
                </div>
              ) : (
                <>
                  <ol className="mt-3 flex flex-wrap gap-2">
                    {row.stages.length === 0 ? (
                      <li className="text-xs text-ink-faint">暂无阶段</li>
                    ) : (
                      row.stages.map((stage, idx) => (
                        <li key={`${row.service_line}-${idx}`} className="rounded bg-surface-muted px-2 py-1 text-xs text-ink">
                          {idx + 1}. {stage}
                        </li>
                      ))
                    )}
                  </ol>
                  {hasAi && (
                    <div className="mt-3 rounded-lg bg-surface-muted/60 p-3 text-xs text-ink-muted">
                      <p className="font-medium text-ink">AI 推荐</p>
                      {ai.agent_tag && <p className="mt-1">智能体标签：{ai.agent_tag}</p>}
                      {ai.flow_template_id && <p>流程模板：{flowLabel ?? ai.flow_template_id}</p>}
                      {ai.chat_hint && <p className="mt-1">对话提示：{ai.chat_hint}</p>}
                      {(ai.quick_prompts?.length ?? 0) > 0 && (
                        <p className="mt-1">快捷提示：{ai.quick_prompts!.join(" · ")}</p>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
