"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { PageHeader } from "@/components/layout/PageHeader";

type OverviewStats = {
  agents: number;
  kbs: number;
  flows: number;
  prompts: number;
  models: number;
  tasks: number;
};

const QUICK_LINKS = [
  { href: "/workbench/agents/chat", label: "对话工作台", desc: "与智能体对话调试" },
  { href: "/workbench/agents", label: "智能体", desc: "查看与管理智能体" },
  { href: "/workbench/kb", label: "知识库", desc: "文档与检索能力" },
  { href: "/workbench/flows", label: "流程编排", desc: "可视化编排与发布" },
  { href: "/workbench/compliance", label: "合规", desc: "敏感词库与内容安全" },
  { href: "/workbench/monitor", label: "监控", desc: "运行指标与告警" },
];

export default function WorkbenchOverviewPage() {
  const { ready } = useRequireAuth();
  const [stats, setStats] = useState<OverviewStats | null>(null);

  useEffect(() => {
    if (!ready) return;
    Promise.all([
      api.listAgents(1, 1),
      api.listKbs(1, 1),
      api.listFlows(1, 1),
      api.listPromptTemplates(1, 1),
      api.listModelConfigs(),
      api.listTasks(1, 1),
    ]).then(([agents, kbs, flows, prompts, models, tasks]) => {
      setStats({
        agents: agents.total,
        kbs: kbs.total,
        flows: flows.total,
        prompts: prompts.total,
        models: models.length,
        tasks: tasks.total,
      });
    });
  }, [ready]);

  if (!stats) {
    return <p className="text-sm text-ink-muted">加载概览…</p>;
  }

  const statCards = [
    { label: "智能体", value: stats.agents, href: "/workbench/agents" },
    { label: "知识库", value: stats.kbs, href: "/workbench/kb" },
    { label: "流程", value: stats.flows, href: "/workbench/flows" },
    { label: "提示词模版", value: stats.prompts, href: "/workbench/prompts" },
    { label: "模型配置", value: stats.models, href: "/workbench/models" },
    { label: "任务", value: stats.tasks, href: "/workbench/tasks" },
  ];

  return (
    <div className="resource-page-shell">
      <PageHeader
        title="工作台概览"
        description="AI 能力资源一览，快速进入常用功能"
      />

      <div className="resource-card-grid mb-8">
        {statCards.map((c) => (
          <Link
            key={c.label}
            href={c.href}
            className="resource-card !min-h-[100px] flex-row items-center justify-between !p-4"
          >
            <span className="text-sm text-ink-muted">{c.label}</span>
            <span className="text-2xl font-bold text-brand">{c.value}</span>
          </Link>
        ))}
      </div>

      <h2 className="mb-3 text-sm font-semibold text-ink">快捷入口</h2>
      <div className="resource-card-grid">
        {QUICK_LINKS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="resource-card"
          >
            <p className="font-medium text-ink">{item.label}</p>
            <p className="mt-1 text-xs text-ink-muted">{item.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
