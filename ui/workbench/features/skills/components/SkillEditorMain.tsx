"use client";

import { CodeEditor, codeLanguageFromPath } from "@/components/editor/CodeEditor";
import { SkillMarkdownSplitEditor } from "@/features/skills/components/SkillMarkdownSplitEditor";
import type { SkillEditorPageVm } from "@/features/skills/hooks/use-skill-editor-page";
import { isMarkdownPath } from "@/features/skills/lib/skill-md";

export function SkillEditorMain({ vm }: { vm: SkillEditorPageVm }) {
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
