"use client";

import { useMemo, useState } from "react";
import { api, getApiErrorMessage } from "@/lib/api";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import {
  SkillImportCategorySelect,
  SkillImportOverwriteToggle,
  type SkillImportDialogProps,
} from "@/features/skills/components/skill-import-dialog-shared";

export function SkillImportLocalDialog({ open, categories, onClose, onDone }: SkillImportDialogProps) {
  const [categoryId, setCategoryId] = useState("");
  const [localPath, setLocalPath] = useState(".data/skills");
  const [overwrite, setOverwrite] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const defaultCat = useMemo(() => categories.find((c) => c.slug === "local_import")?.id ?? categories[0]?.id ?? "", [categories]);
  const effectiveCat = categoryId || defaultCat;

  const submit = async () => {
    if (!effectiveCat || !localPath.trim()) {
      setErr("请填写分类与本地路径");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      const result = await api.importSkillLocal({
        category_id: effectiveCat,
        local_path: localPath.trim(),
        overwrite_existing: overwrite,
      });
      onDone(result);
      onClose();
    } catch (e) {
      setErr(getApiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ResourceDialog
      open={open}
      title="装载本地技能包"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={onClose}>
            取消
          </button>
          <button type="button" className="btn-primary" disabled={busy} onClick={submit}>
            {busy ? "导入中…" : "开始导入"}
          </button>
        </>
      }
    >
      <p className="text-xs text-ink-muted">从服务端可访问的目录扫描技能包（每个子目录须含 SKILL.md）。默认相对 backend 的 .data/skills。</p>
      <SkillImportCategorySelect categories={categories} value={effectiveCat} onChange={setCategoryId} />
      <label className="block text-sm">
        <span className="mb-1 block text-ink-muted">
          本地路径 <span className="text-red-500">*</span>
        </span>
        <input className="input-field w-full" value={localPath} onChange={(e) => setLocalPath(e.target.value)} placeholder=".data/skills" />
      </label>
      <SkillImportOverwriteToggle checked={overwrite} onChange={setOverwrite} />
      {err && <p className="text-xs text-red-600">{err}</p>}
    </ResourceDialog>
  );
}
