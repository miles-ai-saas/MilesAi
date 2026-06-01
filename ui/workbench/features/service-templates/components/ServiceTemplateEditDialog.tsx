"use client";

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import type { BizServiceLineAiConfig, BizServiceLineTemplate, FlowTemplate } from "@/lib/types";

type Props = {
  open: boolean;
  row: BizServiceLineTemplate | null;
  stageText: string;
  setStageText: (value: string) => void;
  aiConfig: BizServiceLineAiConfig;
  setAiConfig: React.Dispatch<React.SetStateAction<BizServiceLineAiConfig>>;
  quickPromptText: string;
  setQuickPromptText: (value: string) => void;
  flowTemplates: FlowTemplate[];
  flowTemplatesLoading: boolean;
  saving: boolean;
  onClose: () => void;
  onSave: () => void;
};

export function ServiceTemplateEditDialog({
  open,
  row,
  stageText,
  setStageText,
  aiConfig,
  setAiConfig,
  quickPromptText,
  setQuickPromptText,
  flowTemplates,
  flowTemplatesLoading,
  saving,
  onClose,
  onSave,
}: Props) {
  return (
    <ResourceDialog
      open={open}
      size="lg"
      title={row ? `编辑 · ${row.label}` : "编辑服务线模板"}
      description={row ? `配置「${row.label}」的阶段流水线与 AI 推荐` : undefined}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost text-sm" onClick={onClose}>
            取消
          </button>
          <button type="button" className="btn-primary text-sm" disabled={saving || !stageText.trim()} onClick={onSave}>
            {saving ? "保存中…" : "保存"}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <label className="block">
          <span className="text-xs font-medium text-ink-muted">阶段名称（每行一个）</span>
          <textarea
            className="input-field mt-1.5 w-full font-mono text-sm"
            rows={Math.max(5, stageText.split("\n").length + 1)}
            value={stageText}
            onChange={(e) => setStageText(e.target.value)}
            placeholder={"需求调研\n方案设计\n执行交付\n复盘总结"}
          />
        </label>

        <fieldset className="space-y-3 rounded-xl border border-line bg-surface-muted/20 p-4">
          <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-ink-muted">AI 推荐配置</legend>
          <label className="block">
            <span className="text-xs text-ink-muted">智能体标签（agent_tag）</span>
            <input
              className="input-field mt-1 w-full text-sm"
              placeholder="如 biz-brand"
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
      </div>
    </ResourceDialog>
  );
}
