"use client";

/**
 * 单技能编辑器（链路 §9，见 lib/chains.ts）：左侧文件树，主区编辑 SKILL.md（或其它文本文件）。
 * 保存调用 putSkillFile；保存 SKILL.md 时后端同步 name/description。
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { CodeEditor, codeLanguageFromPath } from "@/components/editor/CodeEditor";
import { SkillMarkdownSplitEditor } from "@/components/skills/SkillMarkdownSplitEditor";
import { api, getApiErrorMessage } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { isMarkdownPath } from "@/lib/skill-md";
import type { SkillFileNode, SkillPackage } from "@/lib/types";

const DEFAULT_PATH = "SKILL.md";

function flattenFiles(nodes: SkillFileNode[]): SkillFileNode[] {
  const out: SkillFileNode[] = [];
  for (const n of nodes) {
    if (n.type === "file") out.push(n);
    if (n.children?.length) out.push(...flattenFiles(n.children));
  }
  return out;
}

function groupSkillFiles(files: SkillFileNode[]): { label: string; files: SkillFileNode[] }[] {
  const flat = flattenFiles(files);
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

function layoutWarnings(config: Record<string, unknown> | undefined): string[] {
  const layout = config?.layout;
  if (!layout || typeof layout !== "object") return [];
  const warnings = (layout as { warnings?: unknown }).warnings;
  return Array.isArray(warnings) ? warnings.filter((w): w is string => typeof w === "string") : [];
}

function layoutSummary(config: Record<string, unknown> | undefined): {
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

const NEW_FILE_TEMPLATES: Record<string, (name: string) => { path: string; content: string }> = {
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

export default function SkillEditorPage() {
  const params = useParams();
  const id = String(params.id ?? "");
  const { ready } = useRequireAuth();
  const [skill, setSkill] = useState<SkillPackage | null>(null);
  const [files, setFiles] = useState<SkillFileNode[]>([]);
  const [activePath, setActivePath] = useState(DEFAULT_PATH);
  const [content, setContent] = useState("");
  const [saved, setSaved] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [creatingFile, setCreatingFile] = useState(false);
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
        const flat = flattenFiles(tree);
        const path = flat.find((f) => f.path === DEFAULT_PATH)?.path ?? flat[0]?.path ?? DEFAULT_PATH;
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
      const { path, content } = NEW_FILE_TEMPLATES[newFilePrefix](raw);
      await api.putSkillFile(id, { path, content });
      const [s, tree] = await Promise.all([api.getSkillPackage(id), api.listSkillFiles(id)]);
      setSkill(s);
      setFiles(tree);
      setActivePath(path);
      setContent(content);
      setSaved(true);
      setNewFileName("");
    } catch (e) {
      setErr(getApiErrorMessage(e));
    } finally {
      setCreatingFile(false);
    }
  };

  const onDeleteFile = async (path: string) => {
    if (path === DEFAULT_PATH) return;
    if (!window.confirm(`确定删除 ${path}？`)) return;
    setErr("");
    try {
      await api.deleteSkillFile(id, path);
      const [s, tree] = await Promise.all([api.getSkillPackage(id), api.listSkillFiles(id)]);
      setSkill(s);
      setFiles(tree);
      if (activePath === path) {
        setActivePath(DEFAULT_PATH);
        await loadFile(DEFAULT_PATH);
      }
    } catch (e) {
      setErr(getApiErrorMessage(e));
    }
  };

  const onCreatePack = async () => {
    setErr("请在列表页通过「创建技能包」完成打包（后续可接后端打包 API）");
  };

  const fileGroups = groupSkillFiles(files);
  const warnings = layoutWarnings(skill?.config);
  const indexSummary = layoutSummary(skill?.config);

  if (loading) {
    return <p className="p-8 text-sm text-ink-muted">加载中…</p>;
  }

  if (!skill) {
    return (
      <div className="p-8">
        <p className="text-red-600">{err || "技能包不存在"}</p>
        <Link href="/workbench/skills" className="mt-4 text-sm text-brand hover:underline">
          返回列表
        </Link>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      <header className="flex items-center justify-between border-b border-line px-4 py-3">
        <div className="flex items-center gap-3">
          <Link href="/workbench/skills" className="text-ink-muted hover:text-ink">
            ←
          </Link>
          <h1 className="text-lg font-semibold text-ink">{skill.name}</h1>
          <span className="text-xs text-ink-muted">{skill.slug}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-xs ${saved ? "text-green-600" : "text-amber-600"}`}>{saved ? "已保存" : "未保存"}</span>
          <button type="button" className="btn-primary text-sm" disabled={saving} onClick={onSave}>
            {saving ? "保存中…" : "保存"}
          </button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <aside className="w-56 shrink-0 border-r border-line bg-surface-elevated p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-xs font-medium text-ink-muted">文件</p>
            <button type="button" className="text-xs text-brand hover:underline disabled:opacity-50" disabled={reindexing} onClick={() => void onReindex()}>
              {reindexing ? "索引中…" : "刷新索引"}
            </button>
          </div>
          {indexSummary && (
            <p className="mb-2 text-xs text-ink-faint">
              索引：references {indexSummary.references} · scripts {indexSummary.scripts} · assets {indexSummary.assets}
            </p>
          )}
          {warnings.length > 0 && (
            <ul className="mb-3 space-y-1 rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
              {warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}
          <div className="space-y-4 text-sm">
            {fileGroups.map((group) => (
              <div key={group.label}>
                <p className="mb-1 text-xs font-medium text-ink-faint">{group.label}</p>
                <ul className="space-y-1">
                  {group.files.map((f) => (
                    <li key={f.path} className="group flex items-center gap-1">
                      <button
                        type="button"
                        className={`min-w-0 flex-1 truncate rounded px-2 py-1 text-left ${
                          activePath === f.path ? "bg-brand/10 text-brand" : "hover:bg-surface-muted"
                        }`}
                        onClick={() => {
                          setActivePath(f.path);
                          setSaved(false);
                        }}
                      >
                        {f.name}
                      </button>
                      {f.path !== DEFAULT_PATH && (
                        <button
                          type="button"
                          title="删除文件"
                          className="shrink-0 rounded px-1 text-xs text-red-600 opacity-0 hover:bg-red-50 group-hover:opacity-100"
                          onClick={() => void onDeleteFile(f.path)}
                        >
                          ×
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
            {fileGroups.length === 0 && <p className="text-xs text-ink-faint">无文件，保存后将生成 SKILL.md</p>}
          </div>
          <div className="mt-4 space-y-2 border-t border-line pt-3">
            <p className="text-xs font-medium text-ink-muted">新建文件</p>
            <select
              className="w-full rounded border border-line bg-surface px-2 py-1 text-xs"
              value={newFilePrefix}
              onChange={(e) => setNewFilePrefix(e.target.value as "references" | "scripts" | "assets")}
            >
              <option value="references">references/</option>
              <option value="scripts">scripts/</option>
              <option value="assets">assets/</option>
            </select>
            <input
              type="text"
              className="w-full rounded border border-line bg-surface px-2 py-1 text-xs"
              placeholder={newFilePrefix === "scripts" ? "example.py" : "guide.md"}
              value={newFileName}
              onChange={(e) => setNewFileName(e.target.value)}
            />
            <button
              type="button"
              className="w-full rounded border border-line px-2 py-1 text-xs hover:bg-surface-muted disabled:opacity-50"
              disabled={creatingFile || !newFileName.trim()}
              onClick={() => void onCreateFile()}
            >
              {creatingFile ? "创建中…" : "创建并打开"}
            </button>
          </div>
          <button type="button" className="mt-6 w-full text-left text-xs text-red-600 hover:underline" onClick={onCreatePack}>
            创建技能包
          </button>
        </aside>

        <main className="flex min-h-0 min-w-0 flex-1 flex-col p-4">
          {isMarkdownPath(activePath) ? (
            <SkillMarkdownSplitEditor
              path={activePath}
              value={content}
              onChange={(v) => {
                setContent(v);
                setSaved(false);
              }}
            />
          ) : (
            <>
              <p className="mb-2 text-xs text-ink-muted">{activePath}</p>
              <CodeEditor
                fill
                language={codeLanguageFromPath(activePath)}
                value={content}
                onChange={(v) => {
                  setContent(v);
                  setSaved(false);
                }}
                aria-label={`编辑 ${activePath}`}
              />
            </>
          )}
          {err && <p className="mt-2 text-xs text-red-600">{err}</p>}
        </main>
      </div>
    </div>
  );
}
