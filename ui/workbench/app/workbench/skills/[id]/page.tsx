"use client";

/**
 * 单技能编辑器（链路 §9，见 lib/chains.ts）：左侧文件树，主区编辑 SKILL.md（或其它文本文件）。
 * 保存调用 putSkillFile；保存 SKILL.md 时后端同步 name/description。
 */

import { SkillEditorView } from "@/components/skills/SkillEditorView";
import { useSkillEditorPage } from "@/hooks/use-skill-editor-page";

export default function SkillEditorPage() {
  const vm = useSkillEditorPage();
  return <SkillEditorView vm={vm} />;
}
