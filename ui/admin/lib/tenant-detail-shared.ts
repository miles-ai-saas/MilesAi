import type { AdminTenantDetail, BillingPlan } from "@/lib/api";

export const TENANT_STATUS_LABEL: Record<string, string> = {
  active: "活跃",
  trial: "试用",
  suspended: "已停用",
};

export const TENANT_BILL_STATUS_LABEL: Record<string, string> = {
  issued: "待支付",
  paid: "已付",
  void: "已作废",
  draft: "草稿",
};

export function tenantUsagePct(used: number, max: number) {
  return max > 0 ? Math.min(100, Math.round((used / max) * 100)) : 0;
}

export function tenantStatusBadgeClass(status: string) {
  if (status === "active") return "bg-emerald-50 text-emerald-700";
  if (status === "trial") return "bg-sky-50 text-sky-700";
  return "bg-surface-muted text-ink-muted";
}

export function applyPlanQuotas(tenant: AdminTenantDetail, plan: BillingPlan): AdminTenantDetail {
  return {
    ...tenant,
    max_tokens_monthly: plan.max_tokens_monthly,
    max_storage_mb: plan.max_storage_mb,
    max_knowledge_bases: plan.max_knowledge_bases,
    max_agents: plan.max_agents,
    max_flows: plan.max_flows,
  };
}
