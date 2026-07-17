"use client";

import { useCallback, useEffect, useState } from "react";
import { adminApi, type AdminTenant, type BillingPlan } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";
import { planFormFromPlan, type PlanForm } from "@/lib/billing-plan-detail-shared";

export function useBillingPlanDetailPage(id: string) {
  const ready = useRequireAdmin();
  const [plan, setPlan] = useState<BillingPlan | null>(null);
  const [form, setForm] = useState<PlanForm | null>(null);
  const [tenants, setTenants] = useState<AdminTenant[]>([]);
  const [tenantTotal, setTenantTotal] = useState(0);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  const reload = useCallback(async () => {
    const [p, t] = await Promise.all([adminApi.getPlan(id), adminApi.listTenants(1, 10, undefined, id)]);
    setPlan(p);
    setForm(planFormFromPlan(p));
    setTenants(t.items);
    setTenantTotal(t.total);
  }, [id]);

  useEffect(() => {
    if (!ready) return;
    reload().catch(() => setErr("加载失败"));
  }, [ready, reload]);

  const onSave = async () => {
    if (!form) return;
    setSaving(true);
    setErr("");
    try {
      const updated = await adminApi.updatePlan(id, {
        name: form.name.trim(),
        description: form.description.trim() || null,
        price_monthly: Number(form.price_monthly) || 0,
        max_tokens_monthly: form.max_tokens_monthly,
        max_storage_mb: form.max_storage_mb,
        max_knowledge_bases: form.max_knowledge_bases,
        max_agents: form.max_agents,
        max_flows: form.max_flows,
      });
      setPlan(updated);
      setForm(planFormFromPlan(updated));
      setMsg("套餐已保存");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const onToggleActive = async () => {
    if (!plan) return;
    setErr("");
    try {
      const updated = await adminApi.updatePlan(id, { is_active: !plan.is_active });
      setPlan(updated);
      setMsg(updated.is_active ? "套餐已启用" : "套餐已停用");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "操作失败");
    }
  };

  return {
    plan,
    form,
    setForm,
    tenants,
    tenantTotal,
    msg,
    err,
    saving,
    onSave,
    onToggleActive,
  };
}

export type BillingPlanDetailPageVm = ReturnType<typeof useBillingPlanDetailPage>;
