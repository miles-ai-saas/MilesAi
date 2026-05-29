"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { DASHBOARD_STAT_CARDS } from "@/features/dashboard/lib/dashboard-shared";
import { hasPermission } from "@/lib/permissions";
import type { TenantQuota, WorkbenchOverview } from "@/lib/types";

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

  const statCards = useMemo(() => (stats ? DASHBOARD_STAT_CARDS(stats) : []), [stats]);

  return {
    loading: !stats,
    stats,
    quota,
    showQuota,
    statCards,
  };
}

export type DashboardPageVm = ReturnType<typeof useDashboardPage>;
