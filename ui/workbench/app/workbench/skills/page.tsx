"use client";

/** 技能包列表（链路 §3）；SKILL.md 编辑见 skills/[id]（§9）。 */

import { SkillsPageView, useSkillsPage } from "@/features/skills";

export default function SkillsPage() {
  const vm = useSkillsPage();
  return <SkillsPageView vm={vm} />;
}
