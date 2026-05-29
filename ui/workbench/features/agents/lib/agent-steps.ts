/**
 * 智能体对话 `ChatResponse.steps` 的结构化解析（链路 §5，与 backend 步骤 type 对齐）。
 * 由 `ChatMessageThread` 等消费，用于时间线/摘要展示。
 */

export type AgentStepStatus = "success" | "pending" | "error" | "warning" | "skipped" | "neutral";

export interface ParsedAgentStep {
  key: string;
  type: string;
  title: string;
  detail?: string;
  status: AgentStepStatus;
  raw: Record<string, unknown>;
}

const RELEVANCE_LABEL: Record<string, string> = {
  good: "相关",
  poor: "弱相关",
  none: "无相关",
};

const SUMMARY_SKIP_TYPES = new Set(["tool_agent", "graph_start", "planner", "a2a_host", "a2a_rules", "rag_linear"]);

function asStr(v: unknown): string {
  if (v == null) return "";
  return String(v).trim();
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max)}…`;
}

function inferStatus(type: string, step: Record<string, unknown>): AgentStepStatus {
  if (step.error || step.status === "error") return "error";
  if (step.status === "success") return "success";
  if (type === "tool_confirmation_required") return "pending";
  if (type.endsWith("_skip") || type === "subagent_skip" || type === "a2a_skip") return "skipped";
  if (type.endsWith("_error") || type === "a2a_error") return "error";
  if (type === "fallback") return "warning";
  if (type === "retry") return "warning";
  return "neutral";
}

function titleForStep(type: string, step: Record<string, unknown>): { title: string; detail?: string } {
  switch (type) {
    case "retrieve":
      return {
        title: "检索知识库",
        detail: `命中 ${step.hit_count ?? 0} 条${step.top_score != null ? ` · 最高分 ${Number(step.top_score).toFixed(2)}` : ""}`,
      };
    case "grade": {
      const rel = RELEVANCE_LABEL[asStr(step.relevance)] ?? asStr(step.relevance) ?? "—";
      const method = step.grade_method === "llm" ? "LLM 评判" : "分数阈值";
      return { title: "评估相关性", detail: `${rel} · ${method}` };
    }
    case "retry":
      return {
        title: "扩大检索重试",
        detail: `第 ${step.retry_count ?? "?"} 次 · top_k=${step.top_k ?? "?"}`,
      };
    case "generate":
      return {
        title: "生成回答",
        detail: step.hit_count != null ? `基于 ${step.hit_count} 条上下文` : undefined,
      };
    case "fallback":
      return { title: "无足够依据", detail: "使用兜底话术" };
    case "rag_linear":
      return { title: "RAG 检索生成", detail: asStr(step.engine) || "langchain" };

    case "tool_agent":
      if (step.error === "no_tools") return { title: "工具调用", detail: "未找到可用工具" };
      if (step.error === "max_iterations") return { title: "工具调用", detail: "达到最大轮次" };
      return { title: "工具调用引擎", detail: asStr(step.engine) || undefined };

    case "tool_call":
      return {
        title: `调用工具 · ${asStr(step.slug) || "未知"}`,
        detail: step.status === "success" ? "执行成功" : undefined,
      };
    case "tool_execute":
      return {
        title: `执行工具 · ${asStr(step.slug) || "未知"}`,
        detail: step.status === "error" ? "执行失败" : "执行成功",
      };
    case "tool_confirmation_required":
      return { title: `待确认 · ${asStr(step.slug) || "工具"}`, detail: "需用户确认后执行" };

    case "planner":
      return { title: "任务规划", detail: asStr(step.mode) || asStr(step.engine) || undefined };
    case "planner_fallback":
      return { title: "规划降级", detail: asStr(step.reason) || undefined };
    case "plan": {
      const sub = Array.isArray(step.steps) ? step.steps.length : 0;
      return { title: "执行计划", detail: sub > 0 ? `共 ${sub} 个子步骤` : undefined };
    }
    case "subagent_dispatch":
      return {
        title: `委派 · ${asStr(step.sub_agent_name) || "子智能体"}`,
        detail: step.task ? truncate(asStr(step.task), 120) : step.role_hint ? asStr(step.role_hint) : undefined,
      };
    case "subagent":
      return {
        title: `子智能体 · ${asStr(step.sub_agent_name) || asStr(step.tool) || "task"}`,
        detail: step.output_preview ? truncate(asStr(step.output_preview), 120) : undefined,
      };
    case "subagent_skip":
      return { title: "跳过子智能体", detail: asStr(step.reason) || undefined };

    case "graph_start":
      return { title: "启动流程图", detail: asStr(step.engine) || undefined };
    case "flow_node":
      return {
        title: `流程节点 · ${asStr(step.node_type) || asStr(step.node) || "节点"}`,
        detail: asStr(step.node_id) || undefined,
      };

    case "a2a_host":
      if (step.error === "no_peers") return { title: "A2A 宿主", detail: "未配置外部 Agent" };
      if (step.error === "no_model") return { title: "A2A 宿主", detail: "未配置模型" };
      return { title: "A2A 宿主路由", detail: asStr(step.engine) || undefined };
    case "a2a_rules":
      return { title: "A2A 规则匹配", detail: undefined };
    case "a2a_plan": {
      const n = Array.isArray(step.steps) ? step.steps.length : 0;
      return { title: "A2A 执行计划", detail: n > 0 ? `${n} 个 Peer` : undefined };
    }
    case "a2a_peer":
      return {
        title: `外部 Agent · ${asStr(step.peer_name) || asStr(step.peer_id) || "peer"}`,
        detail: step.latency_ms != null ? `${step.latency_ms} ms` : undefined,
      };
    case "a2a_skip":
      return { title: "跳过 A2A Peer", detail: asStr(step.reason) || undefined };
    case "a2a_error":
      return { title: "A2A 调用失败", detail: asStr(step.error) || asStr(step.reason) || undefined };

    default:
      return { title: type || "未知步骤", detail: undefined };
  }
}

export function parseAgentSteps(steps: Record<string, unknown>[] | undefined): ParsedAgentStep[] {
  if (!steps?.length) return [];
  return steps.map((raw, index) => {
    const type = asStr(raw.type) || "unknown";
    const { title, detail } = titleForStep(type, raw);
    return {
      key: `${type}-${index}`,
      type,
      title,
      detail,
      status: inferStatus(type, raw),
      raw,
    };
  });
}

export function buildStepsSummary(parsed: ParsedAgentStep[]): string {
  const labels = parsed
    .filter((s) => !SUMMARY_SKIP_TYPES.has(s.type) || s.status === "error" || s.status === "pending")
    .map((s) => {
      if (s.type === "retrieve") return `检索 ${s.raw.hit_count ?? 0} 条`;
      if (s.type === "tool_call" || s.type === "tool_execute") {
        const slug = asStr(s.raw.slug);
        return slug ? `调用 ${slug}` : s.title;
      }
      if (s.type === "tool_confirmation_required") return `待确认 ${asStr(s.raw.slug) || "工具"}`;
      if (s.type === "subagent_dispatch") return `委派 ${asStr(s.raw.sub_agent_name) || "子智能体"}`;
      if (s.type === "a2a_peer") return `A2A ${asStr(s.raw.peer_name) || "Peer"}`;
      if (s.type === "generate") return "生成回答";
      if (s.type === "fallback") return "兜底回答";
      if (s.status === "error") return `${s.title}失败`;
      return s.title;
    });

  const uniq = Array.from(new Set(labels.filter(Boolean)));
  if (!uniq.length) return `共 ${parsed.length} 步`;
  return uniq.join(" · ");
}

export function formatToolParams(params: Record<string, unknown>): string {
  const entries = Object.entries(params);
  if (!entries.length) return "（无参数）";
  return entries
    .slice(0, 6)
    .map(([k, v]) => `${k}=${truncate(JSON.stringify(v), 40)}`)
    .join(" · ");
}
