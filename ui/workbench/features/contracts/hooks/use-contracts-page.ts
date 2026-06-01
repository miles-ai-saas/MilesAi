"use client";

/** 合同列表页 VM——分页查询、确认删除。 */

import { useCallback } from "react";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useRequireAuth } from "@/lib/auth-store";
import { api } from "@/lib/api";
import type { BizContract } from "@/lib/types";

export function useContractsPage() {
  const { ready } = useRequireAuth();
  const list = usePagedList((page, size) => api.listContracts(page, size), { enabled: ready });
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const handleDelete = useCallback(
    (c: BizContract) => requestConfirm({
      title: "删除合同",
      description: `确定删除「${c.name}」？`,
      onConfirm: async () => { await api.deleteContract(c.id); list.reload(); },
    }),
    [requestConfirm, list],
  );

  return { ready, list, onDelete: handleDelete, confirmDialog };
}

export type ContractsPageVm = ReturnType<typeof useContractsPage>;
