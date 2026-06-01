"use client";

import { useCallback, useState } from "react";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useRequireAuth } from "@/lib/auth-store";
import { api } from "@/lib/api";
import type { BizSupplier } from "@/lib/types";

export function useSuppliersPage() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");

  const list = usePagedList(
    (page, size) => api.listSuppliers(page, size, search || undefined, category || undefined, status || undefined),
    { enabled: ready },
  );

  const { requestConfirm, confirmDialog } = useConfirmAction();

  const handleDelete = useCallback(
    (supplier: BizSupplier) => {
      requestConfirm({
        title: "删除供应商",
        description: `确定删除「${supplier.name}」？`,
        onConfirm: async () => {
          await api.deleteSupplier(supplier.id);
          list.reload();
        },
      });
    },
    [requestConfirm, list],
  );

  return {
    ready,
    search,
    category,
    status,
    onSearch: setSearch,
    onCategory: setCategory,
    onStatus: setStatus,
    list,
    onDelete: handleDelete,
    confirmDialog,
  };
}

export type SuppliersPageVm = ReturnType<typeof useSuppliersPage>;
