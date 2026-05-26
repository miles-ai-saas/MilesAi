"use client";

/** 新建流程：名称、描述、画布模板（链路 §6）。 */
import { useEffect, useState } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { TagPicker } from "@/components/tag/TagPicker";
import {
  RAG_TEMPLATE,
  RAG_TEMPLATE_WITH_GRADE,
} from "@/lib/flow-nodes";
import type { FlowGraph } from "@/lib/types";

export type FlowCreateTemplate = "blank" | "rag" | "rag_grade";

const TEMPLATE_OPTIONS: {
  value: FlowCreateTemplate;
  label: string;
  hint: string;
}[] = [
  { value: "blank", label: "空白画布", hint: "从零拖拽节点" },
  { value: "rag", label: "RAG 问答", hint: "检索 → 提示词 → LLM → 输出" },
  {
    value: "rag_grade",
    label: "RAG + 相关性评分",
    hint: "含评分分支与无命中兜底",
  },
];

function graphForTemplate(template: FlowCreateTemplate): FlowGraph {
  if (template === "rag") return RAG_TEMPLATE;
  if (template === "rag_grade") return RAG_TEMPLATE_WITH_GRADE;
  return { nodes: [], edges: [] };
}

const DEFAULT_NAMES: Record<FlowCreateTemplate, string> = {
  blank: "新流程",
  rag: "RAG 问答流程",
  rag_grade: "RAG 评分流程",
};

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
  const [name, setName] = useState(DEFAULT_NAMES.rag);
  const [description, setDescription] = useState("");
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [template, setTemplate] = useState<FlowCreateTemplate>("rag");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!open) return;
    setTemplate("rag");
    setName(DEFAULT_NAMES.rag);
    setDescription("");
    setTagIds([]);
  }, [open]);

  const onTemplateChange = (next: FlowCreateTemplate) => {
    setTemplate(next);
    setName((prev) => {
      const wasDefault = Object.values(DEFAULT_NAMES).includes(prev);
      return wasDefault ? DEFAULT_NAMES[next] : prev;
    });
  };

  const submit = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    setCreating(true);
    try {
      await onCreate({
        name: trimmed,
        description: description.trim(),
        tag_ids: tagIds,
        graph_json: graphForTemplate(template),
      });
      onClose();
    } finally {
      setCreating(false);
    }
  };

  const disabled = busy || creating;

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
            disabled={disabled || !name.trim()}
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
          <div className="space-y-2">
            {TEMPLATE_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className={`flex cursor-pointer gap-3 rounded-lg border px-3 py-2.5 transition-colors ${
                  template === opt.value
                    ? "border-brand/40 bg-brand-light/20"
                    : "border-line hover:border-line/80"
                }`}
              >
                <input
                  type="radio"
                  name="flow-template"
                  className="mt-1 shrink-0"
                  checked={template === opt.value}
                  disabled={disabled}
                  onChange={() => onTemplateChange(opt.value)}
                />
                <span className="min-w-0">
                  <span className="block text-sm font-medium text-ink">{opt.label}</span>
                  <span className="block text-xs text-ink-muted">{opt.hint}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
      </div>
    </ResourceDialog>
  );
}
