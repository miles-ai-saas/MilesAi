import type { SkillFileNode } from "@/lib/types";

export const SKILL_EDITOR_DEFAULT_PATH = "SKILL.md";

export function flattenSkillFiles(nodes: SkillFileNode[]): SkillFileNode[] {
  const out: SkillFileNode[] = [];
  for (const n of nodes) {
    if (n.type === "file") out.push(n);
    if (n.children?.length) out.push(...flattenSkillFiles(n.children));
  }
  return out;
}

export function groupSkillFiles(files: SkillFileNode[]): { label: string; files: SkillFileNode[] }[] {
  const flat = flattenSkillFiles(files);
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

export function skillLayoutWarnings(config: Record<string, unknown> | undefined): string[] {
  const layout = config?.layout;
  if (!layout || typeof layout !== "object") return [];
  const warnings = (layout as { warnings?: unknown }).warnings;
  return Array.isArray(warnings) ? warnings.filter((w): w is string => typeof w === "string") : [];
}

export function skillLayoutSummary(config: Record<string, unknown> | undefined): {
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

export const SKILL_NEW_FILE_TEMPLATES: Record<string, (name: string) => { path: string; content: string }> = {
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
