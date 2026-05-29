"use client";

import Link from "next/link";
import { SkillEditorHeader } from "@/components/skills/SkillEditorHeader";
import { SkillEditorMain } from "@/components/skills/SkillEditorMain";
import { SkillEditorSidebar } from "@/components/skills/SkillEditorSidebar";
import type { SkillEditorPageVm } from "@/hooks/use-skill-editor-page";

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
