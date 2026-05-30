"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { usePagedList } from "@/hooks/use-paged-list";
import { auditActionOptions, auditDateRangeFromPreset, type AuditDatePreset } from "@/lib/audit-labels";
import { adminApi } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export function useAuditPage() {
  const ready = useRequireAdmin();
  const searchParams = useSearchParams();
  const [actionFilter, setActionFilter] = useState("");
  const [adminFilter, setAdminFilter] = useState("");
  const [tenantFilter, setTenantFilter] = useState("");
  const [datePreset, setDatePreset] = useState<AuditDatePreset>("30d");
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");
  const [metaActions, setMetaActions] = useState<string[]>([]);
  const [metaAdmins, setMetaAdmins] = useState<{ id: string; username: string }[]>([]);

  useEffect(() => {
    const fromUrl = searchParams.get("tenant_id");
    if (fromUrl) setTenantFilter(fromUrl);
  }, [searchParams]);

  useEffect(() => {
    if (!ready) return;
    adminApi
      .getAuditMeta()
      .then((m) => {
        setMetaActions(m.actions);
        setMetaAdmins(m.admins);
      })
      .catch(() => undefined);
  }, [ready]);

  const dateRange = useMemo(() => auditDateRangeFromPreset(datePreset, customFrom, customTo), [datePreset, customFrom, customTo]);
  const filterKey = `${actionFilter}-${adminFilter}-${tenantFilter.trim()}-${datePreset}-${customFrom}-${customTo}`;

  const list = usePagedList(
    useCallback(
      (p, s) =>
        adminApi.listAuditLogs({
          page: p,
          size: s,
          action: actionFilter || undefined,
          admin_id: adminFilter || undefined,
          tenant_id: tenantFilter.trim() || undefined,
          created_from: dateRange.created_from,
          created_to: dateRange.created_to,
        }),
      [actionFilter, adminFilter, tenantFilter, dateRange.created_from, dateRange.created_to],
    ),
    { enabled: ready, resetKey: filterKey },
  );

  const actionOptions = useMemo(() => auditActionOptions(metaActions), [metaActions]);
  const hasActiveFilters = Boolean(actionFilter || adminFilter || tenantFilter.trim() || datePreset !== "30d" || customFrom || customTo);

  return {
    actionFilter,
    setActionFilter,
    adminFilter,
    setAdminFilter,
    tenantFilter,
    setTenantFilter,
    datePreset,
    setDatePreset,
    customFrom,
    setCustomFrom,
    customTo,
    setCustomTo,
    metaAdmins,
    list,
    actionOptions,
    hasActiveFilters,
  };
}

export type AuditPageVm = ReturnType<typeof useAuditPage>;
