"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { CodeEditor, codeLanguageFromPath } from "@/components/editor/CodeEditor";
import { MarkdownPreview } from "@/components/editor/MarkdownPreview";
import type { SkillEditorPageVm } from "@/features/skills/hooks/use-skill-editor-page";
import { SKILL_EDITOR_DEFAULT_PATH } from "@/features/skills/hooks/use-skill-editor-page";
import { isMarkdownPath, parseSkillMd } from "@/features/skills/lib/skill-md";

type SkillMdViewMode = "edit" | "preview" | "split";

function SkillMarkdownSplitEditor({ path, value, onChange }: { path: string; value: string; onChange: (value: string) => void }) {
  const [viewMode, setViewMode] = useState<SkillMdViewMode>("split");
  const { frontmatter, body } = useMemo(() => parseSkillMd(value), [value]);
  const showEdit = viewMode === "edit" || viewMode === "split";
  const showPreview = viewMode === "preview" || viewMode === "split";
  const tabs: { key: SkillMdViewMode; label: string }[] = [
    { key: "edit", label: "编辑" },
    { key: "split", label: "分栏" },
    { key: "preview", label: "预览" },
  ];
  const frontmatterEntries = Object.entries(frontmatter);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-ink-muted">{path}</p>
        <div className="inline-flex rounded-lg border border-line bg-surface-muted/50 p-0.5">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setViewMode(tab.key)}
              className={`rounded-md px-2.5 py-1 text-xs transition ${
                viewMode === tab.key ? "bg-surface font-medium text-brand shadow-sm" : "text-ink-muted hover:text-ink"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>
      <div className={`flex min-h-0 flex-1 gap-3 ${viewMode === "split" ? "flex-col lg:flex-row" : "flex-col"}`}>
        {showEdit && (
          <div className={`flex min-h-0 min-w-0 flex-col ${viewMode === "split" ? "min-h-[240px] flex-1 lg:min-h-0" : "flex-1"}`}>
            <CodeEditor fill language="markdown" value={value} onChange={onChange} aria-label={`编辑 ${path}`} />
          </div>
        )}
        {showPreview && (
          <section
            className={`flex min-h-0 min-w-0 flex-col overflow-hidden rounded-lg border border-line bg-surface ${
              viewMode === "split" ? "min-h-[240px] flex-1 lg:min-h-0" : "flex-1"
            }`}
          >
            <header className="shrink-0 border-b border-line-soft px-4 py-2 text-xs font-medium text-ink-muted">预览</header>
            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
              {frontmatterEntries.length === 0 ? (
                <p className="mb-3 rounded-lg border border-dashed border-line px-3 py-2 text-xs text-ink-faint">
                  无 YAML frontmatter；SKILL.md 建议以 <code className="text-brand">---</code> 块开头。
                </p>
              ) : (
                <dl className="mb-3 space-y-2 rounded-lg border border-line bg-surface-muted/40 px-3 py-2 text-xs">
                  <p className="font-medium text-ink-muted">Frontmatter</p>
                  {frontmatterEntries.map(([key, val]) => (
                    <div key={key} className="grid gap-0.5 sm:grid-cols-[5.5rem_1fr]">
                      <dt className="font-mono text-ink-faint">{key}</dt>
                      <dd className="break-words text-ink">{val || "—"}</dd>
                    </div>
                  ))}
                </dl>
              )}
              <MarkdownPreview content={body} />
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

function SkillEditorHeader({ vm }: { vm: SkillEditorPageVm }) {
  const { skill, saved, saving, onSave } = vm;
  if (!skill) return null;

  return (
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
        <button type="button" className="btn-primary text-sm" disabled={saving} onClick={() => void onSave()}>
          {saving ? "保存中…" : "保存"}
        </button>
      </div>
    </header>
  );
}

function SkillEditorMain({ vm }: { vm: SkillEditorPageVm }) {
  const { activePath, content, updateContent, err } = vm;

  return (
    <main className="flex min-h-0 min-w-0 flex-1 flex-col p-4">
      {isMarkdownPath(activePath) ? (
        <SkillMarkdownSplitEditor path={activePath} value={content} onChange={updateContent} />
      ) : (
        <>
          <p className="mb-2 text-xs text-ink-muted">{activePath}</p>
          <CodeEditor fill language={codeLanguageFromPath(activePath)} value={content} onChange={updateContent} aria-label={`编辑 ${activePath}`} />
        </>
      )}
      {err && <p className="mt-2 text-xs text-red-600">{err}</p>}
    </main>
  );
}

function SkillEditorSidebar({ vm }: { vm: SkillEditorPageVm }) {
  const {
    fileGroups,
    indexSummary,
    warnings,
    activePath,
    selectPath,
    onDeleteFile,
    reindexing,
    onReindex,
    newFilePrefix,
    setNewFilePrefix,
    newFileName,
    setNewFileName,
    creatingFile,
    onCreateFile,
    onCreatePack,
  } = vm;

  return (
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
                    onClick={() => selectPath(f.path)}
                  >
                    {f.name}
                  </button>
                  {f.path !== SKILL_EDITOR_DEFAULT_PATH && (
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
  );
}

export function SkillEditorView({ vm }: { vm: SkillEditorPageVm }) {
  const { loading, skill, err } = vm;

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
      <SkillEditorHeader vm={vm} />
      <div className="flex min-h-0 flex-1">
        <SkillEditorSidebar vm={vm} />
        <SkillEditorMain vm={vm} />
      </div>
    </div>
  );
}
