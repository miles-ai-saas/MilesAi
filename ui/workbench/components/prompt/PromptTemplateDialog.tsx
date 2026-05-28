"use client";

/** 提示词模板表单（链路 §3 + §4）。 */
import { useEffect, useState } from "react";
import { MarkdownPreview } from "@/components/editor/MarkdownPreview";
import { MarkdownSplitEditor } from "@/components/editor/MarkdownSplitEditor";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { TagChips } from "@/components/tag/TagChips";
import { TagPicker } from "@/components/tag/TagPicker";
import { api } from "@/lib/api";
import type { PromptTemplate } from "@/lib/types";

export const DEFAULT_PROMPT_TEMPLATE_CONTENT = "你是企业智能助手，请准确、简洁地回答用户问题。";

export type PromptTemplateDialogMode = "create" | "edit" | "view";

type Props = {
  open: boolean;
  mode: PromptTemplateDialogMode;
  template?: PromptTemplate | null;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
  onRequestEdit?: () => void;
};

export function PromptTemplateDialog({ open, mode, template, onClose, onSaved, onRequestEdit }: Props) {
  const isView = mode === "view";
  const isEdit = mode === "edit";
  const [name, setName] = useState("");
  const [content, setContent] = useState(DEFAULT_PROMPT_TEMPLATE_CONTENT);
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setError("");
    if (template) {
      setName(template.name);
      setContent(template.content);
      setTagIds((template.tags ?? []).map((t) => t.id));
    } else {
      setName("");
      setContent(DEFAULT_PROMPT_TEMPLATE_CONTENT);
      setTagIds([]);
    }
  }, [open, template]);

  const canSave = name.trim().length > 0 && content.trim().length > 0;

  const save = async () => {
    if (isView || !canSave) return;
    setBusy(true);
    setError("");
    try {
      if (isEdit && template) {
        await api.updatePromptTemplate(template.id, {
          name: name.trim(),
          content,
          category_id: null,
          tag_ids: tagIds,
        });
      } else {
        await api.createPromptTemplate(name.trim(), content, undefined, undefined, tagIds);
      }
      await onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  };

  const title = mode === "create" ? "新建提示词模板" : isView ? "查看提示词模板" : "编辑提示词模板";

  return (
    <ResourceDialog
      open={open}
      title={title}
      description="正文支持 Markdown，供智能体 system prompt 与流程节点引用。"
      size="sheet"
      contentMaxWidth="max-w-6xl"
      onClose={onClose}
      footer={
        isView ? (
          <>
            <button type="button" className="btn-ghost" onClick={onClose}>
              关闭
            </button>
            {onRequestEdit && (
              <button type="button" className="btn-primary" onClick={onRequestEdit}>
                编辑
              </button>
            )}
          </>
        ) : (
          <>
            <button type="button" className="btn-ghost" disabled={busy} onClick={onClose}>
              取消
            </button>
            <button type="button" className="btn-primary" disabled={busy || !canSave} onClick={() => void save()}>
              {busy ? "保存中…" : "保存"}
            </button>
          </>
        )
      }
    >
      <div className="flex min-h-[min(720px,calc(100vh-11rem))] flex-col gap-6">
        <section className="shrink-0 space-y-4">
          {isView ? (
            <div className="space-y-4 text-sm">
              <div>
                <p className="text-xs text-ink-muted">模板名称</p>
                <p className="mt-1 font-medium text-ink">{name || "—"}</p>
              </div>
              {(template?.tags?.length ?? 0) > 0 && (
                <div>
                  <p className="mb-1.5 text-xs text-ink-muted">标签</p>
                  <TagChips tags={template?.tags} />
                </div>
              )}
              {template?.category_name && (
                <div>
                  <p className="text-xs text-ink-muted">分类</p>
                  <p className="mt-1 text-ink">{template.category_name}</p>
                </div>
              )}
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block text-sm sm:col-span-2">
                <span className="mb-1 block font-medium text-ink">
                  <span className="text-red-500">*</span> 模板名称
                </span>
                <input className="input-field w-full" placeholder="例如：客服助手 · 系统提示" value={name} onChange={(e) => setName(e.target.value)} />
              </label>
              <label className="block text-sm sm:col-span-2">
                <span className="mb-1 block font-medium text-ink">标签</span>
                <TagPicker value={tagIds} onChange={setTagIds} />
              </label>
            </div>
          )}
        </section>

        <section className="flex min-h-0 flex-1 flex-col gap-2 border-t border-line-soft pt-5">
          <div className="flex shrink-0 flex-wrap items-end justify-between gap-2">
            <div>
              <h3 className="text-sm font-medium text-ink">{!isView && <span className="text-red-500">*</span>} 提示词正文</h3>
              {!isView && <p className="mt-0.5 text-xs text-ink-faint">Markdown 格式 · 支持标题、列表、代码块与 GFM 表格</p>}
            </div>
          </div>
          {isView ? (
            <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-line bg-surface">
              <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
                <MarkdownPreview content={content} emptyHint="（空正文）" />
              </div>
            </section>
          ) : (
            <MarkdownSplitEditor
              fill
              value={content}
              onChange={setContent}
              ariaLabel="提示词模板 Markdown 正文"
              defaultViewMode="split"
              className="min-h-0 flex-1"
            />
          )}
        </section>

        {error && <p className="shrink-0 text-sm text-red-600">{error}</p>}
      </div>
    </ResourceDialog>
  );
}
