"use client";

/** 新建流程：名称、描述、画布模板（GET /flows/templates）。 */
import { useEffect, useState } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { TagPicker } from "@/components/tag/TagPicker";
import { useFlowTemplates } from "@/hooks/use-flow-templates";
import type { FlowGraph, FlowTemplate } from "@/lib/types";

type Props = {
  open: boolean;
  busy?: boolean;
  onClose: () => void;
  onCreate: (payload: {
    name: string;
    description: string;
    tag_ids: string[];
    graph_json: FlowGraph;
  }) => Promise<void>;
};

export function FlowCreateDialog({ open, busy = false, onClose, onCreate }: Props) {
  const { templates, defaultTemplate, loading: templatesLoading } = useFlowTemplates(open);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [templateId, setTemplateId] = useState<string>("rag");
  const [creating, setCreating] = useState(false);

  const selected =
    templates.find((t) => t.id === templateId) ?? defaultTemplate ?? templates[0] ?? null;

  useEffect(() => {
    if (!open || templates.length === 0) return;
    const initial = defaultTemplate ?? templates[0];
    setTemplateId(initial.id);
    setName(initial.default_name);
    setDescription("");
    setTagIds([]);
  }, [open, templates, defaultTemplate]);

  const onTemplateChange = (next: FlowTemplate) => {
    setTemplateId(next.id);
    setName((prev) => {
      const wasDefault = templates.some((t) => t.default_name === prev);
      return wasDefault ? next.default_name : prev;
    });
  };

  const submit = async () => {
    const trimmed = name.trim();
    if (!trimmed || !selected) return;
    setCreating(true);
    try {
      await onCreate({
        name: trimmed,
        description: description.trim(),
        tag_ids: tagIds,
        graph_json: selected.graph_json,
      });
      onClose();
    } finally {
      setCreating(false);
    }
  };

  const disabled = busy || creating || templatesLoading;

  return (
    <ResourceDialog
      open={open}
      title="新建流程"
      description="填写基本信息并选择初始画布模板，创建后可在编辑器中继续编排。"
      size="md"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" disabled={disabled} onClick={onClose}>
            取消
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={disabled || !name.trim() || !selected}
            onClick={() => void submit()}
          >
            {creating ? "创建中…" : "创建并编辑"}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <label className="block text-sm">
          <span className="mb-1 block text-ink-muted">流程名称</span>
          <input
            className="input-field w-full"
            placeholder="流程名称"
            value={name}
            maxLength={128}
            disabled={disabled}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-ink-muted">描述（可选）</span>
          <textarea
            className="input-field min-h-[72px] w-full resize-y"
            placeholder="用途说明，将展示在列表卡片上"
            value={description}
            disabled={disabled}
            rows={2}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-ink-muted">标签</span>
          <TagPicker value={tagIds} onChange={setTagIds} disabled={disabled} />
        </label>
        <fieldset className="space-y-2">
          <legend className="text-sm text-ink-muted">初始模板</legend>
          {templatesLoading && templates.length === 0 ? (
            <p className="text-xs text-ink-muted">加载模板…</p>
          ) : templates.length === 0 ? (
            <p className="text-xs text-ink-muted">模板加载失败，请刷新后重试。</p>
          ) : (
            <div className="space-y-2">
              {templates.map((opt) => (
                <label
                  key={opt.id}
                  className={`flex cursor-pointer gap-3 rounded-lg border px-3 py-2.5 transition-colors ${
                    templateId === opt.id
                      ? "border-brand/40 bg-brand-light/20"
                      : "border-line hover:border-line/80"
                  }`}
                >
                  <input
                    type="radio"
                    name="flow-template"
                    className="mt-1 shrink-0"
                    checked={templateId === opt.id}
                    disabled={disabled}
                    onChange={() => onTemplateChange(opt)}
                  />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-ink">{opt.label}</span>
                    <span className="block text-xs text-ink-muted">{opt.hint}</span>
                  </span>
                </label>
              ))}
            </div>
          )}
        </fieldset>
      </div>
    </ResourceDialog>
  );
}
