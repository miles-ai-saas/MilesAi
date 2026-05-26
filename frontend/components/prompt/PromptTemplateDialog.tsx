"use client";

import { useEffect, useState } from "react";
import { MarkdownSplitEditor } from "@/components/editor/MarkdownSplitEditor";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { TagPicker } from "@/components/tag/TagPicker";
import { api } from "@/lib/api";
import type { PromptTemplate } from "@/lib/types";

export const DEFAULT_PROMPT_TEMPLATE_CONTENT =
  "你是企业智能助手，请准确、简洁地回答用户问题。";

type Props = {
  open: boolean;
  template?: PromptTemplate | null;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
};

export function PromptTemplateDialog({ open, template, onClose, onSaved }: Props) {
  const isEdit = Boolean(template);
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
    if (!canSave) return;
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

  return (
    <ResourceDialog
      open={open}
      title={isEdit ? "编辑提示词模板" : "新建提示词模板"}
      description="正文支持 Markdown，供智能体 system prompt 与流程节点引用。"
      size="sheet"
      contentMaxWidth="max-w-6xl"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" disabled={busy} onClick={onClose}>
            取消
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={busy || !canSave}
            onClick={() => void save()}
          >
            {busy ? "保存中…" : "保存"}
          </button>
        </>
      }
    >
      <div className="flex min-h-[min(720px,calc(100vh-11rem))] flex-col gap-6">
        <section className="shrink-0 space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm sm:col-span-2">
              <span className="mb-1 block font-medium text-ink">
                <span className="text-red-500">*</span> 模板名称
              </span>
              <input
                className="input-field w-full"
                placeholder="例如：客服助手 · 系统提示"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label className="block text-sm sm:col-span-2">
              <span className="mb-1 block font-medium text-ink">标签</span>
              <TagPicker value={tagIds} onChange={setTagIds} />
            </label>
          </div>
        </section>

        <section className="flex min-h-0 flex-1 flex-col gap-2 border-t border-line-soft pt-5">
          <div className="flex shrink-0 flex-wrap items-end justify-between gap-2">
            <div>
              <h3 className="text-sm font-medium text-ink">
                <span className="text-red-500">*</span> 提示词正文
              </h3>
              <p className="mt-0.5 text-xs text-ink-faint">
                Markdown 格式 · 支持标题、列表、代码块与 GFM 表格
              </p>
            </div>
          </div>
          <MarkdownSplitEditor
            fill
            value={content}
            onChange={setContent}
            ariaLabel="提示词模板 Markdown 正文"
            defaultViewMode="split"
            className="min-h-0 flex-1"
          />
        </section>

        {error && <p className="shrink-0 text-sm text-red-600">{error}</p>}
      </div>
    </ResourceDialog>
  );
}
