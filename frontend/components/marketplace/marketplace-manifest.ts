/** 解析应用 manifest 中的 resources，供详情抽屉展示。 */

export type ManifestResourceItem = {
  key: string;
  label: string;
  name: string;
  hint?: string;
};

const RESOURCE_LABELS: Record<string, string> = {
  knowledge_base: "知识库",
  flow: "流程",
  agent: "智能体",
};

export function manifestResourceItems(manifest: Record<string, unknown>): ManifestResourceItem[] {
  const resources = (manifest.resources ?? manifest) as Record<string, unknown>;
  const items: ManifestResourceItem[] = [];

  for (const key of ["knowledge_base", "flow", "agent"] as const) {
    const raw = resources[key];
    if (!raw || typeof raw !== "object") continue;
    const obj = raw as Record<string, unknown>;
    const name = String(obj.name ?? "—");
    let hint: string | undefined;
    if (key === "agent") {
      const parts: string[] = [];
      if (obj.bind_kb) parts.push("绑知识库");
      if (obj.bind_flow) parts.push("绑流程");
      if (parts.length) hint = parts.join(" · ");
    }
    if (key === "flow" && obj.auto_publish === false) {
      hint = hint ? `${hint} · 安装后不自动发布` : "安装后不自动发布";
    }
    items.push({
      key,
      label: RESOURCE_LABELS[key] ?? key,
      name,
      hint,
    });
  }

  return items;
}
