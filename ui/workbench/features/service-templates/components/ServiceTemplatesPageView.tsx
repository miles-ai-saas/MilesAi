"use client";

import Link from "next/link";
import { BizPageHero } from "@/features/business-dashboard/components/BizPageHero";
import { BizListPageSkeleton } from "@/features/business/components/BizListSkeleton";
import { ServiceTemplateEditDialog } from "@/features/service-templates/components/ServiceTemplateEditDialog";
import type { ServiceTemplatesPageVm } from "@/features/service-templates/hooks/use-service-templates-page";
import { StatChip } from "@/components/ui/StatChip";
import type { BizServiceLineTemplate } from "@/lib/types";

const SOURCE_LABELS: Record<string, string> = {
  tenant: "租户自定义",
  global: "系统默认",
  none: "未配置",
};

const SOURCE_BADGE: Record<string, string> = {
  tenant: "bg-emerald-50 text-emerald-700",
  global: "bg-surface-muted text-ink-muted",
  none: "bg-amber-50 text-amber-700",
};

function hasAiConfig(row: BizServiceLineTemplate) {
  const ai = row.ai_config ?? {};
  return Boolean(
    ai.agent_tag ||
      ai.flow_template_id ||
      ai.chat_hint ||
      (ai.quick_prompts?.length ?? 0) > 0,
  );
}

function StageTimeline({ stages }: { stages: string[] }) {
  if (stages.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-line bg-surface-muted/20 px-4 py-8 text-center">
        <p className="text-sm text-ink-muted">尚未配置阶段流水线</p>
        <p className="mt-1 text-xs text-ink-faint">可手动编辑，或从模板市场一键应用</p>
      </div>
    );
  }

  return (
    <ol className="space-y-0">
      {stages.map((stage, idx) => (
        <li key={`${stage}-${idx}`} className="relative flex gap-4 pb-5 last:pb-0">
          {idx < stages.length - 1 ? (
            <span className="absolute left-3 top-7 h-[calc(100%-0.75rem)] w-px bg-line" aria-hidden />
          ) : null}
          <span className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand text-xs font-semibold text-white shadow-sm">
            {idx + 1}
          </span>
          <div className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-3 py-2.5 shadow-sm">
            <p className="text-sm font-medium text-ink">{stage}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

function ServiceLineNavButton({
  row,
  active,
  onSelect,
}: {
  row: BizServiceLineTemplate;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full rounded-lg px-3 py-2.5 text-left transition ${
        active ? "bg-brand/10 ring-1 ring-brand/30" : "hover:bg-surface-muted/80"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <span className={`text-sm font-medium ${active ? "text-brand" : "text-ink"}`}>{row.label}</span>
        <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] ${SOURCE_BADGE[row.source] ?? SOURCE_BADGE.none}`}>
          {row.source === "tenant" ? "自定义" : row.source === "global" ? "默认" : "空"}
        </span>
      </div>
      <div className="mt-1.5 flex flex-wrap gap-1.5 text-[10px] text-ink-faint">
        <span>{row.stages.length > 0 ? `${row.stages.length} 阶段` : "无阶段"}</span>
        {hasAiConfig(row) ? <span className="text-brand/80">· AI</span> : null}
      </div>
    </button>
  );
}

function ServiceLineDetailPanel({
  row,
  flowLabel,
  canWrite,
  saving,
  onEdit,
  onReset,
}: {
  row: BizServiceLineTemplate;
  flowLabel?: string;
  canWrite: boolean;
  saving: boolean;
  onEdit: () => void;
  onReset: () => void;
}) {
  const ai = row.ai_config ?? {};
  const hasAi = hasAiConfig(row);
  const marketHref = `/business/template-market?service_line=${encodeURIComponent(row.service_line)}`;

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line pb-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold text-ink">{row.label}</h2>
            <span className={`rounded-full px-2 py-0.5 text-xs ${SOURCE_BADGE[row.source] ?? SOURCE_BADGE.none}`}>
              {SOURCE_LABELS[row.source] ?? row.source}
            </span>
          </div>
          <p className="mt-1 text-xs text-ink-muted">
            {row.service_line}
            {row.source === "tenant"
              ? " · 已覆盖系统默认，新建工作包将继承此流水线"
              : " · 当前使用系统默认配置"}
          </p>
        </div>
        {canWrite && (
          <div className="flex flex-wrap items-center gap-2">
            <Link href={marketHref} className="btn-ghost text-xs">
              从市场应用
            </Link>
            <button type="button" className="btn-primary text-xs" onClick={onEdit}>
              编辑配置
            </button>
            {row.source === "tenant" && (
              <button
                type="button"
                className="btn-ghost text-xs text-ink-muted"
                disabled={saving}
                onClick={onReset}
              >
                恢复默认
              </button>
            )}
          </div>
        )}
      </div>

      <div className="mt-5 grid gap-6 xl:grid-cols-2">
        <section>
          <div className="mb-3 flex items-center justify-between gap-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">阶段流水线</h3>
            <span className="text-xs text-ink-faint">{row.stages.length} 步</span>
          </div>
          <StageTimeline stages={row.stages} />
        </section>

        <section>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-muted">AI 推荐</h3>
          {hasAi ? (
            <div className="space-y-3 rounded-xl border border-line bg-surface-muted/30 p-4 text-sm">
              {ai.agent_tag && (
                <div>
                  <p className="text-xs text-ink-muted">智能体标签</p>
                  <p className="mt-0.5 font-mono text-ink">{ai.agent_tag}</p>
                </div>
              )}
              {ai.flow_template_id && (
                <div>
                  <p className="text-xs text-ink-muted">流程模板</p>
                  <p className="mt-0.5 text-ink">{flowLabel ?? ai.flow_template_id}</p>
                </div>
              )}
              {ai.chat_hint && (
                <div>
                  <p className="text-xs text-ink-muted">对话提示</p>
                  <p className="mt-0.5 leading-relaxed text-ink-muted">{ai.chat_hint}</p>
                </div>
              )}
              {(ai.quick_prompts?.length ?? 0) > 0 && (
                <div>
                  <p className="text-xs text-ink-muted">快捷提示</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {ai.quick_prompts!.map((prompt, i) => (
                      <span
                        key={i}
                        className="rounded-full border border-line bg-surface px-2.5 py-0.5 text-xs text-ink"
                      >
                        {prompt}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-line bg-surface-muted/20 px-4 py-8 text-center">
              <p className="text-sm text-ink-muted">未配置 AI 推荐</p>
              <p className="mt-1 text-xs text-ink-faint">编辑时可设置智能体标签与快捷提示</p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function PageSkeleton() {
  return <BizListPageSkeleton />;
}

export function ServiceTemplatesPageView({ vm }: { vm: ServiceTemplatesPageVm }) {
  const {
    ready,
    items,
    loading,
    selectedLine,
    setSelectedLine,
    selectedRow,
    editingRow,
    customizedCount,
    configuredCount,
    aiReadyCount,
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
    return <PageSkeleton />;
  }

  const flowLabel = selectedRow
    ? flowTemplates.find((t) => t.id === selectedRow.ai_config?.flow_template_id)?.label
    : undefined;
  const progressPct = items.length > 0 ? Math.round((customizedCount / items.length) * 100) : 0;

  return (
    <div className="w-full">
      <BizPageHero
        flowStep="projects"
        compact
        title="服务线模板"
        subtitle="为八条服务线配置阶段流水线与 AI 推荐，新建工作包时自动继承"
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Link href="/business/template-market" className="btn-ghost text-xs">
              浏览模板市场
            </Link>
            {canWriteProject && (
              <Link href="/business/template-market?tab=mine" className="btn-primary text-xs">
                发布到市场
              </Link>
            )}
          </div>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <StatChip
          label="租户自定义"
          value={`${customizedCount}/${items.length}`}
          hint={`完成度 ${progressPct}%`}
        />
        <StatChip label="已配置阶段" value={String(configuredCount)} hint="至少包含一个阶段" />
        <StatChip label="已配 AI 推荐" value={String(aiReadyCount)} hint="含智能体或快捷提示" />
      </div>

      <div className="mb-4 flex gap-2 overflow-x-auto pb-1 lg:hidden">
        {items.map((row) => (
          <button
            key={row.service_line}
            type="button"
            className={`shrink-0 rounded-full px-3 py-1.5 text-xs ${
              row.service_line === selectedLine
                ? "bg-brand text-white"
                : "border border-line bg-surface text-ink-muted"
            }`}
            onClick={() => setSelectedLine(row.service_line)}
          >
            {row.label}
          </button>
        ))}
      </div>

      <div className="card overflow-hidden">
        <div className="flex min-h-[520px] flex-col lg:flex-row">
          <aside className="hidden shrink-0 border-b border-line bg-surface-muted/20 p-3 lg:block lg:w-64 lg:border-b-0 lg:border-r">
            <p className="px-2 py-1 text-xs font-semibold uppercase tracking-wide text-ink-muted">服务线</p>
            <nav className="mt-1 space-y-1">
              {items.map((row) => (
                <ServiceLineNavButton
                  key={row.service_line}
                  row={row}
                  active={row.service_line === selectedLine}
                  onSelect={() => setSelectedLine(row.service_line)}
                />
              ))}
            </nav>
            <div className="mt-4 px-2">
              <div className="h-1.5 overflow-hidden rounded-full bg-surface-muted">
                <div
                  className="h-full rounded-full bg-brand transition-all"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
              <p className="mt-1.5 text-[10px] text-ink-faint">自定义 {customizedCount} / {items.length}</p>
            </div>
          </aside>

          <main className="flex-1 p-5 lg:p-6">
            {selectedRow ? (
              <ServiceLineDetailPanel
                row={selectedRow}
                flowLabel={flowLabel}
                canWrite={canWriteProject}
                saving={saving}
                onEdit={() => startEdit(selectedRow)}
                onReset={() => void resetTemplate(selectedRow.service_line)}
              />
            ) : (
              <p className="text-sm text-ink-faint">请选择一条服务线</p>
            )}
          </main>
        </div>
      </div>

      <ServiceTemplateEditDialog
        open={Boolean(editingLine)}
        row={editingRow}
        stageText={stageText}
        setStageText={setStageText}
        aiConfig={aiConfig}
        setAiConfig={setAiConfig}
        quickPromptText={quickPromptText}
        setQuickPromptText={setQuickPromptText}
        flowTemplates={flowTemplates}
        flowTemplatesLoading={flowTemplatesLoading}
        saving={saving}
        onClose={cancelEdit}
        onSave={() => void saveEdit()}
      />
    </div>
  );
}
