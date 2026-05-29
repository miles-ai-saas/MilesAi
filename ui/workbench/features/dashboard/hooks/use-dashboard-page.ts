"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { hasPermission } from "@/lib/permissions";
import type { TenantQuota, WorkbenchOverview } from "@/lib/types";

function dashboardStatCards(stats: {
  agents: number;
  kbs: number;
  flows: number;
  prompts: number;
  models: number;
  tasks: number;
}) {
  return [
    { label: "智能体", value: stats.agents, href: "/workbench/agents" },
    { label: "知识库", value: stats.kbs, href: "/workbench/kb" },
    { label: "流程", value: stats.flows, href: "/workbench/flows" },
    { label: "提示词模版", value: stats.prompts, href: "/workbench/prompts" },
    { label: "模型配置", value: stats.models, href: "/workbench/models" },
    { label: "任务", value: stats.tasks, href: "/workbench/tasks" },
  ];
}

export function useDashboardPage() {
  const { ready, user } = useRequireAuth();
  const [stats, setStats] = useState<WorkbenchOverview | null>(null);
  const [quota, setQuota] = useState<TenantQuota | null>(null);
  const showQuota = hasPermission(user, "system:quota:read");

  useEffect(() => {
    if (!ready) return;
    void api
      .getWorkbenchOverview()
      .then(setStats)
      .catch(() => setStats(null));
  }, [ready]);

  useEffect(() => {
    if (!ready || !showQuota) return;
    void api
      .getSystemQuota()
      .then(setQuota)
      .catch(() => setQuota(null));
  }, [ready, showQuota]);

  const statCards = useMemo(() => (stats ? dashboardStatCards(stats) : []), [stats]);

  return {
    loading: !stats,
    stats,
    quota,
    showQuota,
    statCards,
  };
}

export type DashboardPageVm = ReturnType<typeof useDashboardPage>;
