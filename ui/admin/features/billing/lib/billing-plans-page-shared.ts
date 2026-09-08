export const BILLING_PLANS_PAGE_DESCRIPTION = "定义租户可绑定的计费方案与默认配额";

export const DEFAULT_NEW_PLAN_QUOTAS = {
  max_knowledge_bases: 10,
  max_storage_mb: 10240,
  max_tokens_monthly: 1_000_000,
  max_agents: 20,
  max_flows: 20,
  is_active: true,
} as const;
