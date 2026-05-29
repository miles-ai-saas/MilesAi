/**
 * SKILL.md frontmatter 解析（链路 §9，与 backend `parse_skill_md` 对齐）。
 * 技能包编辑页保存时由 API 回写 DB 元数据。
 */

export type SkillMdFrontmatter = Record<string, string>;

const FRONTMATTER_RE = /^---\s*\n([\s\S]*?)\n---\s*\n?/;

export function parseSkillMd(content: string): {
  frontmatter: SkillMdFrontmatter;
  body: string;
} {
  const text = content ?? "";
  const match = FRONTMATTER_RE.exec(text);
  if (!match) {
    return { frontmatter: {}, body: text.trim() };
  }

  const frontmatter: SkillMdFrontmatter = {};
  for (const line of match[1].split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes(":")) continue;
    const colon = trimmed.indexOf(":");
    const key = trimmed.slice(0, colon).trim();
    let val = trimmed.slice(colon + 1).trim();
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    }
    if (key) frontmatter[key] = val;
  }

  return { frontmatter, body: text.slice(match[0].length).trim() };
}

export function isMarkdownPath(path: string): boolean {
  const lower = path.toLowerCase();
  return lower.endsWith(".md") || lower.endsWith(".markdown");
}
