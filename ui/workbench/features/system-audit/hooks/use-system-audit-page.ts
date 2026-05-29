"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useAuditMeta } from "@/hooks/use-audit-meta";
import { auditActionFilterOptions, auditResourceTypeFilterOptions } from "@/lib/audit-labels";

export function useSystemAuditPage() {
  const { ready } = useRequireAuth();
  const auditMeta = useAuditMeta(ready);
  const [actionFilter, setActionFilter] = useState("");
  const [resourceFilter, setResourceFilter] = useState("");

  const list = usePagedList(
    useCallback(
      (p, s) =>
        api.listAuditLogs(p, s, {
          action: actionFilter || undefined,
          resource_type: resourceFilter || undefined,
        }),
      [actionFilter, resourceFilter],
    ),
    { enabled: ready, resetKey: `${actionFilter}-${resourceFilter}` },
  );

  const actionOptions = auditActionFilterOptions(auditMeta);
  const resourceOptions = auditResourceTypeFilterOptions(auditMeta);
  const hasActiveFilters = Boolean(actionFilter || resourceFilter);

  const clearFilters = () => {
    setActionFilter("");
    setResourceFilter("");
  };

  return {
    auditMeta,
    actionFilter,
    setActionFilter,
    resourceFilter,
    setResourceFilter,
    list,
    actionOptions,
    resourceOptions,
    hasActiveFilters,
    clearFilters,
  };
}

export type SystemAuditPageVm = ReturnType<typeof useSystemAuditPage>;
