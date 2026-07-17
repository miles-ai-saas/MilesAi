"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { adminApi, type AdminTenantDetail, type BillingPlan, type TenantBill } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";
import { applyPlanQuotas } from "@/lib/tenant-detail-shared";

export function useTenantDetailPage(id: string) {
  const router = useRouter();
  const ready = useRequireAdmin();
  const [tenant, setTenant] = useState<AdminTenantDetail | null>(null);
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [bills, setBills] = useState<TenantBill[]>([]);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [savingSub, setSavingSub] = useState(false);
  const [savingQuota, setSavingQuota] = useState(false);

  const reload = useCallback(async () => {
    const [t, p, usage, billRes] = await Promise.all([
      adminApi.getTenant(id),
      adminApi.listPlans(),
      adminApi.getTenantUsage(id),
      adminApi.listBills(1, 5, id),
    ]);
    setTenant({ ...t, usage });
    setPlans(p);
    setBills(billRes.items);
  }, [id]);

  useEffect(() => {
    if (!ready) return;
    void reload().catch(() => undefined);
  }, [ready, reload]);

  const activePlans = useMemo(() => plans.filter((p) => p.is_active || p.id === tenant?.plan_id), [plans, tenant?.plan_id]);
  const selectedPlan = useMemo(() => plans.find((p) => p.id === tenant?.plan_id) ?? null, [plans, tenant?.plan_id]);

  const saveSubscription = async () => {
    if (!tenant) return;
    setSavingSub(true);
    setErr("");
    try {
      await adminApi.updateTenant(id, {
        status: tenant.status,
        plan_id: tenant.plan_id,
        is_active: tenant.is_active,
      });
      setMsg("订阅信息已保存");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSavingSub(false);
    }
  };

  const saveQuota = async () => {
    if (!tenant) return;
    setSavingQuota(true);
    setErr("");
    try {
      await adminApi.updateQuota(id, {
        max_tokens_monthly: tenant.max_tokens_monthly,
        max_storage_mb: tenant.max_storage_mb,
        max_knowledge_bases: tenant.max_knowledge_bases,
        max_agents: tenant.max_agents,
        max_flows: tenant.max_flows,
      });
      setMsg("配额已更新");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "更新失败");
    } finally {
      setSavingQuota(false);
    }
  };

  const onApplyPlanQuota = () => {
    if (!tenant || !selectedPlan) return;
    setTenant(applyPlanQuotas(tenant, selectedPlan));
    setMsg(`已填入套餐「${selectedPlan.name}」的配额，请点击「保存配额」生效`);
  };

  const onDelete = async () => {
    if (!tenant || !confirm(`确定删除租户「${tenant.name}」？将清空其业务数据。`)) return;
    await adminApi.deleteTenant(id);
    router.push("/tenants");
  };

  const copyTenantId = async () => {
    try {
      await navigator.clipboard.writeText(id);
      setMsg("已复制租户 ID");
    } catch {
      setErr("复制失败");
    }
  };

  return {
    id,
    tenant,
    setTenant,
    plans,
    bills,
    msg,
    err,
    savingSub,
    savingQuota,
    activePlans,
    selectedPlan,
    saveSubscription,
    saveQuota,
    onApplyPlanQuota,
    onDelete,
    copyTenantId,
  };
}

export type TenantDetailPageVm = ReturnType<typeof useTenantDetailPage>;
