/** Eval 展示文案与 expected 表单转换。 */

export type ExpectedMode = "exact" | "contains" | "none";

export const EVAL_RUN_STATUS_LABELS: Record<string, string> = {
  pending: "待启动",
  running: "运行中",
  success: "成功",
  failed: "失败",
  cancelled: "已取消",
};

export const EVAL_SCORING_MODE_LABELS: Record<string, string> = {
  auto: "自动",
  rules: "规则",
  llm_judge: "LLM Judge",
};

export const EVAL_SCORING_MODE_OPTIONS = [
  { value: "auto", label: "自动" },
  { value: "rules", label: "规则" },
  { value: "llm_judge", label: "LLM Judge" },
] as const;

export function evalRunStatusLabel(status: string): string {
  return EVAL_RUN_STATUS_LABELS[status] || status;
}

export function evalScoringModeLabel(mode: string): string {
  return EVAL_SCORING_MODE_LABELS[mode] || mode;
}

export function isEvalRunActive(status: string): boolean {
  return status === "pending" || status === "running";
}

/** 从后端 expected JSON 解析为一期表单（仅 exact / contains）。 */
export function parseExpectedForm(expected?: Record<string, unknown> | null): {
  mode: ExpectedMode;
  value: string;
} {
  if (!expected || typeof expected !== "object") {
    return { mode: "none", value: "" };
  }
  if (typeof expected.exact === "string") {
    return { mode: "exact", value: expected.exact };
  }
  if (typeof expected.contains === "string") {
    return { mode: "contains", value: expected.contains };
  }
  return { mode: "none", value: "" };
}

export function buildExpectedPayload(mode: ExpectedMode, value: string): Record<string, unknown> | null {
  const v = value.trim();
  if (mode === "none" || !v) return null;
  if (mode === "exact") return { exact: v };
  return { contains: v };
}

export function formatExpectedPreview(expected?: Record<string, unknown> | null): string {
  const { mode, value } = parseExpectedForm(expected);
  if (mode === "none" || !value) return "—";
  const label = mode === "exact" ? "精确匹配" : "包含";
  const short = value.length > 40 ? `${value.slice(0, 40)}…` : value;
  return `${label}: ${short}`;
}

export function formatRunSummary(summary?: Record<string, unknown> | null): string {
  if (!summary || typeof summary !== "object") return "—";
  const total = typeof summary.total === "number" ? summary.total : null;
  const passed = typeof summary.passed === "number" ? summary.passed : null;
  const failed = typeof summary.failed === "number" ? summary.failed : null;
  const errored = typeof summary.errored === "number" ? summary.errored : null;
  const parts: string[] = [];
  if (passed !== null) parts.push(`通过 ${passed}`);
  if (failed !== null) parts.push(`失败 ${failed}`);
  if (errored !== null) parts.push(`错误 ${errored}`);
  if (total !== null) parts.push(`共 ${total}`);
  return parts.length ? parts.join(" · ") : "—";
}
