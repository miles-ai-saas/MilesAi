"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, getApiErrorMessage } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import type { SkillFileNode, SkillPackage } from "@/lib/types";

export const SKILL_EDITOR_DEFAULT_PATH = "SKILL.md";

export function flattenSkillFiles(nodes: SkillFileNode[]): SkillFileNode[] {
  const out: SkillFileNode[] = [];
  for (const n of nodes) {
    if (n.type === "file") out.push(n);
    if (n.children?.length) out.push(...flattenSkillFiles(n.children));
  }
  return out;
}

export function groupSkillFiles(files: SkillFileNode[]): { label: string; files: SkillFileNode[] }[] {
  const flat = flattenSkillFiles(files);
  const root = flat.filter((f) => !f.path.includes("/"));
  const refs = flat.filter((f) => f.path.startsWith("references/"));
  const scripts = flat.filter((f) => f.path.startsWith("scripts/"));
  const assets = flat.filter((f) => f.path.startsWith("assets/"));
  const other = flat.filter(
    (f) => f.path.includes("/") && !f.path.startsWith("references/") && !f.path.startsWith("scripts/") && !f.path.startsWith("assets/"),
  );
  const groups: { label: string; files: SkillFileNode[] }[] = [];
  if (root.length) groups.push({ label: "根目录", files: root });
  if (refs.length) groups.push({ label: "references/", files: refs });
  if (scripts.length) groups.push({ label: "scripts/", files: scripts });
  if (assets.length) groups.push({ label: "assets/", files: assets });
  if (other.length) groups.push({ label: "其它", files: other });
  return groups;
}

export function skillLayoutWarnings(config: Record<string, unknown> | undefined): string[] {
  const layout = config?.layout;
  if (!layout || typeof layout !== "object") return [];
  const warnings = (layout as { warnings?: unknown }).warnings;
  return Array.isArray(warnings) ? warnings.filter((w): w is string => typeof w === "string") : [];
}

export function skillLayoutSummary(config: Record<string, unknown> | undefined): {
  references: number;
  scripts: number;
  assets: number;
} | null {
  const layout = config?.layout;
  if (!layout || typeof layout !== "object") return null;
  const l = layout as {
    reference_index?: unknown;
    script_index?: unknown;
    asset_index?: unknown;
  };
  return {
    references: Array.isArray(l.reference_index) ? l.reference_index.length : 0,
    scripts: Array.isArray(l.script_index) ? l.script_index.length : 0,
    assets: Array.isArray(l.asset_index) ? l.asset_index.length : 0,
  };
}

export const SKILL_NEW_FILE_TEMPLATES: Record<string, (name: string) => { path: string; content: string }> = {
  references: (name) => ({
    path: `references/${name.endsWith(".md") ? name : `${name}.md`}`,
    content: `# ${name.replace(/\.md$/i, "")}\n\n`,
  }),
  scripts: (name) => ({
    path: `scripts/${name.endsWith(".py") ? name : `${name}.py`}`,
    content: `"""${name.replace(/\.py$/i, "")} — 由 skill_run_script 沙箱执行。"""


def run(params):
    return params
`,
  }),
  assets: (name) => ({
    path: `assets/${name.endsWith(".md") ? name : `${name}.md`}`,
    content: `# ${name.replace(/\.md$/i, "")}\n\n`,
  }),
};

export function useSkillEditorPage(id: string) {
  const { ready } = useRequireAuth();
  const [skill, setSkill] = useState<SkillPackage | null>(null);
  const [files, setFiles] = useState<SkillFileNode[]>([]);
  const [activePath, setActivePath] = useState(SKILL_EDITOR_DEFAULT_PATH);
  const [content, setContent] = useState("");
  const [saved, setSaved] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [creatingFile, setCreatingFile] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [newFilePrefix, setNewFilePrefix] = useState<"references" | "scripts" | "assets">("references");
  const [newFileName, setNewFileName] = useState("");
  const [err, setErr] = useState("");

  const loadFile = useCallback(
    async (path: string) => {
      const f = await api.getSkillFile(id, path);
      setContent(f.content);
      setSaved(true);
    },
    [id],
  );

  useEffect(() => {
    if (!ready || !id) return;
    setLoading(true);
    setErr("");
    Promise.all([api.getSkillPackage(id), api.listSkillFiles(id)])
      .then(([s, tree]) => {
        setSkill(s);
        setFiles(tree);
        const flat = flattenSkillFiles(tree);
        const path = flat.find((f) => f.path === SKILL_EDITOR_DEFAULT_PATH)?.path ?? flat[0]?.path ?? SKILL_EDITOR_DEFAULT_PATH;
        setActivePath(path);
        return api.getSkillFile(id, path);
      })
      .then((f) => setContent(f.content))
      .catch((e) => setErr(getApiErrorMessage(e)))
      .finally(() => setLoading(false));
  }, [ready, id]);

  useEffect(() => {
    if (!ready || !id || loading) return;
    void loadFile(activePath).catch((e) => setErr(getApiErrorMessage(e)));
  }, [activePath, ready, id, loading, loadFile]);

  const onSave = async () => {
    setSaving(true);
    setErr("");
    try {
      await api.putSkillFile(id, { path: activePath, content });
      setSaved(true);
      const [s, tree] = await Promise.all([api.getSkillPackage(id), api.listSkillFiles(id)]);
      setSkill(s);
      setFiles(tree);
    } catch (e) {
      setErr(getApiErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  const onReindex = async () => {
    setReindexing(true);
    setErr("");
    try {
      const s = await api.reindexSkillPackage(id);
      setSkill(s);
    } catch (e) {
      setErr(getApiErrorMessage(e));
    } finally {
      setReindexing(false);
    }
  };

  const onCreateFile = async () => {
    const raw = newFileName.trim();
    if (!raw) return;
    setCreatingFile(true);
    setErr("");
    try {
      const { path, content: fileContent } = SKILL_NEW_FILE_TEMPLATES[newFilePrefix](raw);
      await api.putSkillFile(id, { path, content: fileContent });
      const [s, tree] = await Promise.all([api.getSkillPackage(id), api.listSkillFiles(id)]);
      setSkill(s);
      setFiles(tree);
      setActivePath(path);
      setContent(fileContent);
      setSaved(true);
      setNewFileName("");
    } catch (e) {
      setErr(getApiErrorMessage(e));
    } finally {
      setCreatingFile(false);
    }
  };

  const onDeleteFile = async (path: string) => {
    if (path === SKILL_EDITOR_DEFAULT_PATH) return;
    if (!window.confirm(`确定删除 ${path}？`)) return;
    setErr("");
    try {
      await api.deleteSkillFile(id, path);
      const [s, tree] = await Promise.all([api.getSkillPackage(id), api.listSkillFiles(id)]);
      setSkill(s);
      setFiles(tree);
      if (activePath === path) {
        setActivePath(SKILL_EDITOR_DEFAULT_PATH);
        await loadFile(SKILL_EDITOR_DEFAULT_PATH);
      }
    } catch (e) {
      setErr(getApiErrorMessage(e));
    }
  };

  const onCreatePack = async () => {
    setExporting(true);
    setErr("");
    try {
      const blob = await api.exportSkillZipBlob(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${skill?.slug || id}.zip`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setErr(getApiErrorMessage(e));
    } finally {
      setExporting(false);
    }
  };

  const selectPath = (path: string) => {
    setActivePath(path);
    setSaved(false);
  };

  const updateContent = (value: string) => {
    setContent(value);
    setSaved(false);
  };

  const fileGroups = useMemo(() => groupSkillFiles(files), [files]);
  const warnings = useMemo(() => skillLayoutWarnings(skill?.config), [skill?.config]);
  const indexSummary = useMemo(() => skillLayoutSummary(skill?.config), [skill?.config]);

  return {
    skill,
    loading,
    err,
    saved,
    saving,
    activePath,
    content,
    fileGroups,
    warnings,
    indexSummary,
    reindexing,
    creatingFile,
    exporting,
    newFilePrefix,
    setNewFilePrefix,
    newFileName,
    setNewFileName,
    onSave,
    onReindex,
    onCreateFile,
    onDeleteFile,
    onCreatePack,
    selectPath,
    updateContent,
  };
}

export type SkillEditorPageVm = ReturnType<typeof useSkillEditorPage>;
