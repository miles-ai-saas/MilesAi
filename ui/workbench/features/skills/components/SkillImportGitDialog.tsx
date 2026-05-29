"use client";

import { useMemo, useState } from "react";
import { api, getApiErrorMessage } from "@/lib/api";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import {
  SkillImportCategorySelect,
  SkillImportOverwriteToggle,
  type SkillImportDialogProps,
} from "@/features/skills/components/skill-import-dialog-shared";

export function SkillImportGitDialog({ open, categories, onClose, onDone }: SkillImportDialogProps) {
  const [categoryId, setCategoryId] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [overwrite, setOverwrite] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const defaultCat = useMemo(() => categories.find((c) => c.slug === "git_import")?.id ?? categories[0]?.id ?? "", [categories]);
  const effectiveCat = categoryId || defaultCat;

  const submit = async () => {
    if (!effectiveCat || !repoUrl.trim()) {
      setErr("请填写分类与仓库地址");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      const result = await api.importSkillGit({
        category_id: effectiveCat,
        repo_url: repoUrl.trim(),
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
      title="下载 Git 技能包"
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
        克隆仓库后扫描：若存在 <code className="text-brand">skills/</code> 则从其加载，否则扫描仓库根目录。
      </p>
      <SkillImportCategorySelect categories={categories} value={effectiveCat} onChange={setCategoryId} />
      <label className="block text-sm">
        <span className="mb-1 block text-ink-muted">
          仓库地址 <span className="text-red-500">*</span>
        </span>
        <input className="input-field w-full" value={repoUrl} onChange={(e) => setRepoUrl(e.target.value)} placeholder="https://github.com/user/repo.git" />
      </label>
      <SkillImportOverwriteToggle checked={overwrite} onChange={setOverwrite} />
      {err && <p className="text-xs text-red-600">{err}</p>}
    </ResourceDialog>
  );
}
