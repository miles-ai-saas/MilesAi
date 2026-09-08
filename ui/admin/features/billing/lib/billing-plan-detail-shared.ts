import type { BillingPlan } from "@/lib/api";

export type PlanForm = {
  name: string;
  description: string;
  price_monthly: string;
  max_tokens_monthly: number;
  max_storage_mb: number;
  max_knowledge_bases: number;
  max_agents: number;
  max_flows: number;
};

export function planFormFromPlan(p: BillingPlan): PlanForm {
  return {
    name: p.name,
    description: p.description ?? "",
    price_monthly: String(p.price_monthly),
    max_tokens_monthly: p.max_tokens_monthly,
    max_storage_mb: p.max_storage_mb,
    max_knowledge_bases: p.max_knowledge_bases,
    max_agents: p.max_agents,
    max_flows: p.max_flows,
  };
}
