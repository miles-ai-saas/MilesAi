"use client";

import { useCallback, useEffect, useState } from "react";
import { usePagedList } from "@/hooks/use-paged-list";
import { adminApi, type BillingPlan } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export function useTenantsPage() {
  const ready = useRequireAdmin();
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [name, setName] = useState("");
  const [planId, setPlanId] = useState("");

  const list = usePagedList(
    useCallback((p, s) => adminApi.listTenants(p, s, statusFilter || undefined), [statusFilter]),
    { enabled: ready, resetKey: statusFilter },
  );

  useEffect(() => {
    if (!ready) return;
    adminApi
      .listPlans()
      .then(setPlans)
      .catch(() => undefined);
  }, [ready]);

  const create = async () => {
    if (!name.trim()) return;
    await adminApi.createTenant({
      name: name.trim(),
      plan_id: planId || null,
      status: "active",
    });
    setName("");
    await list.reload();
  };

  return {
    plans,
    statusFilter,
    setStatusFilter,
    name,
    setName,
    planId,
    setPlanId,
    list,
    create,
  };
}

export type TenantsPageVm = ReturnType<typeof useTenantsPage>;
