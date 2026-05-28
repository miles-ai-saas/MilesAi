"use client";

/** 流程名称、描述与标签编辑（链路 §6）。 */
import { useEffect, useState } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { TagPicker } from "@/components/tag/TagPicker";

type Props = {
  open: boolean;
  title?: string;
  initialName?: string;
  initialDescription?: string | null;
  initialTagIds?: string[];
  busy?: boolean;
  onClose: () => void;
  onSave: (name: string, description: string, tagIds: string[]) => Promise<void>;
};

export function FlowMetaDialog({
  open,
  title = "流程基本信息",
  initialName = "",
  initialDescription = "",
  initialTagIds = [],
  busy = false,
  onClose,
  onSave,
}: Props) {
  const [name, setName] = useState(initialName);
  const [description, setDescription] = useState(initialDescription ?? "");
  const [tagIds, setTagIds] = useState<string[]>(initialTagIds);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setName(initialName);
    setDescription(initialDescription ?? "");
    setTagIds(initialTagIds);
  }, [open, initialName, initialDescription, initialTagIds]);

  const submit = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    setSaving(true);
    try {
      await onSave(trimmed, description.trim(), tagIds);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  const disabled = busy || saving;

  return (
    <ResourceDialog
      open={open}
      title={title}
      description="名称、描述与标签会在流程列表卡片上展示，便于检索与协作。"
      size="md"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" disabled={disabled} onClick={onClose}>
            取消
          </button>
          <button type="button" className="btn-primary" disabled={disabled || !name.trim()} onClick={() => void submit()}>
            {saving ? "保存中…" : "保存"}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <label className="block text-sm">
          <span className="mb-1 block text-ink-muted">流程名称</span>
          <input
            className="input-field w-full"
            placeholder="例如：客服 RAG 问答"
            value={name}
            maxLength={128}
            disabled={disabled}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-ink-muted">描述（可选）</span>
          <textarea
            className="input-field min-h-[88px] w-full resize-y"
            placeholder="用途、绑定场景、注意事项等"
            value={description}
            disabled={disabled}
            rows={3}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-ink-muted">标签</span>
          <TagPicker value={tagIds} onChange={setTagIds} disabled={disabled} />
        </label>
      </div>
    </ResourceDialog>
  );
}
