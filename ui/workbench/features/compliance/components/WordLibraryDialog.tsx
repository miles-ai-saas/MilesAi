"use client";

/** 词库创建/编辑（链路 §13）。 */
import { useEffect, useState } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { api } from "@/lib/api";
import type { WordLibrary } from "@/lib/types";

type Props = {
  open: boolean;
  library?: WordLibrary | null;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
};

export function WordLibraryDialog({ open, library, onClose, onSaved }: Props) {
  const isEdit = Boolean(library);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setError("");
    if (library) {
      setName(library.name);
      setDescription(library.description ?? "");
      setIsActive(library.is_active);
    } else {
      setName("");
      setDescription("");
      setIsActive(true);
    }
  }, [open, library]);

  const save = async () => {
    if (!name.trim()) return;
    setBusy(true);
    setError("");
    try {
      if (isEdit && library) {
        await api.updateWordLibrary(library.id, {
          name: name.trim(),
          description: description.trim() || null,
          is_active: isActive,
        });
      } else {
        await api.createWordLibrary({
          name: name.trim(),
          description: description.trim() || undefined,
          is_active: isActive,
        });
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
      title={isEdit ? "编辑词库" : "新建词库"}
      description="词库用于归类敏感词条；仅「参与扫描」的词库会在对话中生效。"
      size="md"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" disabled={busy} onClick={onClose}>
            取消
          </button>
          <button type="button" className="btn-primary" disabled={busy || !name.trim()} onClick={() => void save()}>
            {busy ? "保存中…" : "保存"}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <label className="block space-y-1 text-sm">
          <span className="text-xs text-ink-muted">词库名称</span>
          <input className="input-field w-full" value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：通用违禁、广告法" />
        </label>
        <label className="block space-y-1 text-sm">
          <span className="text-xs text-ink-muted">说明（可选）</span>
          <textarea className="input-field min-h-[80px] w-full resize-y" value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} className="rounded border-line text-brand" />
          <span>启用词库（停用后库内词条不参与扫描）</span>
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>
    </ResourceDialog>
  );
}
