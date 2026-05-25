"use client";

/**
 * 三种批量导入弹窗：本地目录、ZIP（须含 skills/）、Git 克隆。
 * overwrite 勾选对应 API overwrite_existing（覆盖同名 slug）。
 */

import { useMemo, useState } from "react";
import { api, getApiErrorMessage } from "@/lib/api";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import type { SkillImportResult, SysCategory } from "@/lib/types";

type BaseProps = {
  open: boolean;
  categories: SysCategory[];
  onClose: () => void;
  onDone: (result: SkillImportResult) => void;
};

function CategorySelect({
  categories,
  value,
  onChange,
}: {
  categories: SysCategory[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-ink-muted">
        技能分类 <span className="text-red-500">*</span>
      </span>
      <select className="input-field w-full" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">请选择</option>
        {categories.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function OverwriteToggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-start gap-3 text-sm">
      <input
        type="checkbox"
        className="mt-1"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>
        <span className="font-medium text-ink">覆盖已有同名技能</span>
        <span className="mt-1 block text-xs text-ink-muted">
          开启后，若存在同名技能包，将以新导入内容覆盖原有数据；关闭则跳过同名项。
        </span>
      </span>
    </label>
  );
}

export function SkillImportLocalDialog({ open, categories, onClose, onDone }: BaseProps) {
  const [categoryId, setCategoryId] = useState("");
  const [localPath, setLocalPath] = useState(".data/skills");
  const [overwrite, setOverwrite] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const defaultCat = useMemo(
    () => categories.find((c) => c.slug === "local_import")?.id ?? categories[0]?.id ?? "",
    [categories],
  );

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
      <p className="text-xs text-ink-muted">
        从服务端可访问的目录扫描技能包（每个子目录须含 SKILL.md）。默认相对 backend 的 .data/skills。
      </p>
      <CategorySelect categories={categories} value={effectiveCat} onChange={setCategoryId} />
      <label className="block text-sm">
        <span className="mb-1 block text-ink-muted">
          本地路径 <span className="text-red-500">*</span>
        </span>
        <input
          className="input-field w-full"
          value={localPath}
          onChange={(e) => setLocalPath(e.target.value)}
          placeholder=".data/skills"
        />
      </label>
      <OverwriteToggle checked={overwrite} onChange={setOverwrite} />
      {err && <p className="text-xs text-red-600">{err}</p>}
    </ResourceDialog>
  );
}

export function SkillImportZipDialog({ open, categories, onClose, onDone }: BaseProps) {
  const [categoryId, setCategoryId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [overwrite, setOverwrite] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const defaultCat = useMemo(
    () => categories.find((c) => c.slug === "zip_import")?.id ?? categories[0]?.id ?? "",
    [categories],
  );
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
        须为 .zip，解压后包含 <code className="text-brand">skills/</code> 目录，其下每个技能文件夹含{" "}
        <code className="text-brand">SKILL.md</code>（≤100MB）。
      </p>
      <CategorySelect categories={categories} value={effectiveCat} onChange={setCategoryId} />
      <label className="block text-sm">
        <span className="mb-1 block text-ink-muted">压缩包</span>
        <input
          type="file"
          accept=".zip"
          className="input-field w-full"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
      </label>
      <OverwriteToggle checked={overwrite} onChange={setOverwrite} />
      {err && <p className="text-xs text-red-600">{err}</p>}
    </ResourceDialog>
  );
}

export function SkillImportGitDialog({ open, categories, onClose, onDone }: BaseProps) {
  const [categoryId, setCategoryId] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [overwrite, setOverwrite] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const defaultCat = useMemo(
    () => categories.find((c) => c.slug === "git_import")?.id ?? categories[0]?.id ?? "",
    [categories],
  );
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
      <CategorySelect categories={categories} value={effectiveCat} onChange={setCategoryId} />
      <label className="block text-sm">
        <span className="mb-1 block text-ink-muted">
          仓库地址 <span className="text-red-500">*</span>
        </span>
        <input
          className="input-field w-full"
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          placeholder="https://github.com/user/repo.git"
        />
      </label>
      <OverwriteToggle checked={overwrite} onChange={setOverwrite} />
      {err && <p className="text-xs text-red-600">{err}</p>}
    </ResourceDialog>
  );
}
