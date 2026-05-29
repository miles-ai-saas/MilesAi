"use client";

import { useCallback, useEffect, useState } from "react";
import { adminApi, type BillingPlan } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";
import { DEFAULT_NEW_PLAN_QUOTAS } from "@/lib/billing-plans-page-shared";

export function useBillingPlansPage() {
  const ready = useRequireAdmin();
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [showPlanForm, setShowPlanForm] = useState(false);
  const [planCode, setPlanCode] = useState("");
  const [planName, setPlanName] = useState("");
  const [planPrice, setPlanPrice] = useState("0");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const reload = useCallback(async () => {
    setPlans(await adminApi.listPlans());
  }, []);

  useEffect(() => {
    if (!ready) return;
    reload().catch(() => undefined);
  }, [ready, reload]);

  const onCreatePlan = async () => {
    setErr("");
    setMsg("");
    try {
      await adminApi.createPlan({
        code: planCode.trim(),
        name: planName.trim(),
        price_monthly: Number(planPrice) || 0,
        ...DEFAULT_NEW_PLAN_QUOTAS,
      });
      setShowPlanForm(false);
      setPlanCode("");
      setPlanName("");
      setMsg("套餐已创建");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "创建失败");
    }
  };

  const togglePlanActive = async (plan: BillingPlan) => {
    await adminApi.updatePlan(plan.id, { is_active: !plan.is_active });
    setMsg(plan.is_active ? "套餐已停用" : "套餐已启用");
    await reload();
  };

  return {
    plans,
    showPlanForm,
    setShowPlanForm,
    planCode,
    setPlanCode,
    planName,
    setPlanName,
    planPrice,
    setPlanPrice,
    msg,
    err,
    onCreatePlan,
    togglePlanActive,
  };
}

export type BillingPlansPageVm = ReturnType<typeof useBillingPlansPage>;
