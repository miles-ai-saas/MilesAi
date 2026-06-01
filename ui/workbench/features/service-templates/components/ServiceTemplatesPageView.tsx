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
        subtitle="配置八条服务线的阶段流水线，新建工作包时自动继承"
      />

      <div className="space-y-3">
        {items.map((row) => {
          const editing = editingLine === row.service_line;
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
                      编辑阶段
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
                <div className="mt-3 space-y-2">
                  <label className="block">
                    <span className="text-xs text-ink-muted">阶段名称（每行一个）</span>
                    <textarea
                      className="input-field mt-1 w-full font-mono text-sm"
                      rows={Math.max(4, stageText.split("\n").length + 1)}
                      value={stageText}
                      onChange={(e) => setStageText(e.target.value)}
                    />
                  </label>
                  <div className="flex gap-2">
                    <button type="button" className="btn-primary text-sm" disabled={saving} onClick={() => void saveEdit()}>
                      {saving ? "保存中…" : "保存"}
                    </button>
                    <button type="button" className="btn-ghost text-sm" onClick={cancelEdit}>取消</button>
                  </div>
                </div>
              ) : (
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
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
