import type { QuotaMetric } from "@/lib/types";

export const DASHBOARD_QUICK_LINKS = [
  { href: "/workbench/agents/chat", label: "对话工作台", desc: "与智能体对话调试" },
  { href: "/workbench/agents", label: "智能体", desc: "查看与管理智能体" },
  { href: "/workbench/kb", label: "知识库", desc: "文档与检索能力" },
  { href: "/workbench/flows", label: "流程编排", desc: "可视化编排与发布" },
  { href: "/workbench/compliance", label: "合规", desc: "敏感词库与内容安全" },
  { href: "/workbench/monitor", label: "监控", desc: "运行指标与告警" },
] as const;

export function quotaLabel(metric: QuotaMetric) {
  if (metric.max <= 0) return `${metric.used}${metric.unit ? ` ${metric.unit}` : ""}`;
  return `${metric.used} / ${metric.max}${metric.unit ? ` ${metric.unit}` : ""}`;
}

export const DASHBOARD_STAT_CARDS = (stats: {
  agents: number;
  kbs: number;
  flows: number;
  prompts: number;
  models: number;
  tasks: number;
}) => [
  { label: "智能体", value: stats.agents, href: "/workbench/agents" },
  { label: "知识库", value: stats.kbs, href: "/workbench/kb" },
  { label: "流程", value: stats.flows, href: "/workbench/flows" },
  { label: "提示词模版", value: stats.prompts, href: "/workbench/prompts" },
  { label: "模型配置", value: stats.models, href: "/workbench/models" },
  { label: "任务", value: stats.tasks, href: "/workbench/tasks" },
];
