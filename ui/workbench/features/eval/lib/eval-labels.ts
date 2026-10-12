/** Eval 展示文案与 expected 表单转换。 */

export type ExpectedMode = "exact" | "contains" | "rubric" | "none";

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

export const EXPECTED_MODE_OPTIONS = [
  { value: "exact", label: "精确匹配" },
  { value: "contains", label: "包含子串" },
  { value: "rubric", label: "评分标准（LLM Judge）" },
  { value: "none", label: "不校验" },
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

/** 从后端 expected JSON 解析为表单（exact / contains / rubric）。 */
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
  if (typeof expected.rubric === "string") {
    return { mode: "rubric", value: expected.rubric };
  }
  return { mode: "none", value: "" };
}

/**
 * 构造 expected 写回载荷。
 * 编辑时保留 `_source`（升格溯源），避免更新 exact/contains/rubric 时冲掉 lineage。
 */
export function buildExpectedPayload(
  mode: ExpectedMode,
  value: string,
  previous?: Record<string, unknown> | null,
): Record<string, unknown> | null {
  const v = value.trim();
  let base: Record<string, unknown> | null = null;
  if (mode !== "none" && v) {
    if (mode === "exact") base = { exact: v };
    else if (mode === "contains") base = { contains: v };
    else if (mode === "rubric") base = { rubric: v };
  }
  const source = previous && typeof previous._source === "object" ? previous._source : null;
  if (!base) return null;
  if (source) return { ...base, _source: source };
  return base;
}

export function formatExpectedPreview(expected?: Record<string, unknown> | null): string {
  const { mode, value } = parseExpectedForm(expected);
  if (mode === "none" || !value) return "—";
  const label =
    mode === "exact" ? "精确匹配" : mode === "contains" ? "包含" : mode === "rubric" ? "评分标准" : "期望";
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
