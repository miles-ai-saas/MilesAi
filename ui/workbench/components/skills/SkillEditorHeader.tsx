"use client";

import Link from "next/link";
import type { SkillEditorPageVm } from "@/hooks/use-skill-editor-page";

export function SkillEditorHeader({ vm }: { vm: SkillEditorPageVm }) {
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
