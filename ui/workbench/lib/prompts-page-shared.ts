export const PROMPTS_PAGE_DESC = "管理系统提示词（Markdown），供智能体 system prompt 与流程编排复用；支持按名称、正文或标签筛选。";

export function promptContentPreview(text: string, max = 120): string {
  const t = text.trim().replace(/\s+/g, " ");
  if (!t) return "（空正文）";
  if (t.length <= max) return t;
  return `${t.slice(0, max)}…`;
}

export function exportPromptTemplate(t: { name: string; content: string; category_id?: string | null; tags?: { id: string }[] }) {
  const pkg = {
    version: "1.0",
    name: t.name,
    content: t.content,
    category_id: t.category_id,
    tag_ids: t.tags?.map((tg) => tg.id) ?? [],
  };
  const blob = new Blob([JSON.stringify(pkg, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${t.name.replace(/[^a-zA-Z0-9\u4e00-\u9fff]/g, "_")}.json`;
  a.click();
  URL.revokeObjectURL(url);
}
