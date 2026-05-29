export const SKILLS_PAGE_DESC = "管理 Cursor 风格 SKILL.md 技能目录；支持本地目录、ZIP 与 Git 导入，在智能体中绑定后注入系统提示。";

export function formatSkillUpdated(iso: string) {
  try {
    const d = new Date(iso);
    return d.toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
