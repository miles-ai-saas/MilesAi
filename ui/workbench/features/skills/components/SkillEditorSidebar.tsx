"use client";

import type { SkillEditorPageVm } from "@/features/skills/hooks/use-skill-editor-page";
import { SKILL_EDITOR_DEFAULT_PATH } from "@/features/skills/lib/skill-editor-shared";

export function SkillEditorSidebar({ vm }: { vm: SkillEditorPageVm }) {
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
