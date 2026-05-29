"use client";

import { useMemo, useState } from "react";
import { api, getApiErrorMessage } from "@/lib/api";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import {
  SkillImportCategorySelect,
  SkillImportOverwriteToggle,
  type SkillImportDialogProps,
} from "@/features/skills/components/skill-import-dialog-shared";

export function SkillImportZipDialog({ open, categories, onClose, onDone }: SkillImportDialogProps) {
  const [categoryId, setCategoryId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [overwrite, setOverwrite] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const defaultCat = useMemo(() => categories.find((c) => c.slug === "zip_import")?.id ?? categories[0]?.id ?? "", [categories]);
  const effectiveCat = categoryId || defaultCat;

  const submit = async () => {
    if (!effectiveCat || !file) {
      setErr("请选择分类并上传 .zip 文件");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      const result = await api.importSkillZip(effectiveCat, file, overwrite);
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
      title="导入技能压缩包"
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
      <p className="text-xs text-ink-muted">
        须为 .zip，解压后包含 <code className="text-brand">skills/</code> 目录，其下每个技能文件夹含 <code className="text-brand">SKILL.md</code>（≤100MB）。
      </p>
      <SkillImportCategorySelect categories={categories} value={effectiveCat} onChange={setCategoryId} />
      <label className="block text-sm">
        <span className="mb-1 block text-ink-muted">压缩包</span>
        <input type="file" accept=".zip" className="input-field w-full" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </label>
      <SkillImportOverwriteToggle checked={overwrite} onChange={setOverwrite} />
      {err && <p className="text-xs text-red-600">{err}</p>}
    </ResourceDialog>
  );
}
