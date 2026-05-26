"use client";

/** 新建空白技能包（链路 §9）。 */
/** 创建空白技能包：选择分类后 POST /skill-packages/blank，由列表页跳转编辑器。 */

import { useState } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { TagPicker } from "@/components/tag/TagPicker";
import type { SysCategory } from "@/lib/types";

type Props = {
  open: boolean;
  categories: SysCategory[];
  onClose: () => void;
  onSubmit: (name: string, description: string, categoryId: string, tagIds: string[]) => Promise<void>;
};

export function SkillCreateBlankDialog({ open, categories, onClose, onSubmit }: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const generalId =
    categories.find((c) => c.slug === "general")?.id ?? categories[0]?.id ?? "";
  const effectiveCat = categoryId || generalId;

  const save = async () => {
    if (!name.trim() || !effectiveCat) return;
    setBusy(true);
    try {
      await onSubmit(name.trim(), description.trim(), effectiveCat, tagIds);
      setName("");
      setDescription("");
      onClose();
    } finally {
      setBusy(false);
    }
  };

  return (
    <ResourceDialog
      open={open}
      title="创建技能包"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={onClose}>
            取消
          </button>
          <button type="button" className="btn-primary" disabled={busy} onClick={save}>
            创建
          </button>
        </>
      }
    >
      <input
        className="input-field w-full"
        placeholder="技能名称"
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <input
        className="input-field w-full"
        placeholder="描述（可选）"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      <label className="block text-sm">
        <span className="mb-1 block text-ink-muted">分类</span>
        <select
          className="input-field w-full"
          value={effectiveCat}
          onChange={(e) => setCategoryId(e.target.value)}
        >
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      <label className="block text-sm">
        <span className="mb-1 block text-ink-muted">标签</span>
        <TagPicker value={tagIds} onChange={setTagIds} />
      </label>
    </ResourceDialog>
  );
}
