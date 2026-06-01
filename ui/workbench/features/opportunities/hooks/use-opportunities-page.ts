"use client";

/** 商机列表页 VM——分页查询、确认删除。 */

import { useCallback } from "react";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useRequireAuth } from "@/lib/auth-store";
import { api } from "@/lib/api";
import type { BizOpportunity } from "@/lib/types";

export function useOpportunitiesPage() {
  const { ready } = useRequireAuth();
  const list = usePagedList((page, size) => api.listOpportunities(page, size), { enabled: ready });
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const handleDelete = useCallback(
    (o: BizOpportunity) => requestConfirm({
      title: "删除商机",
      description: `确定删除「${o.name}」？`,
      onConfirm: async () => { await api.deleteOpportunity(o.id); list.reload(); },
    }),
    [requestConfirm, list],
  );

  return { ready, list, onDelete: handleDelete, confirmDialog };
}

export type OpportunitiesPageVm = ReturnType<typeof useOpportunitiesPage>;
