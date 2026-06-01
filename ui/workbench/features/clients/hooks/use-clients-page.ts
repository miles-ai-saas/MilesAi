"use client";

/** 客户列表页 VM——分页查询、关键词搜索、确认删除。 */

import { useCallback, useState } from "react";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useRequireAuth } from "@/lib/auth-store";
import { api } from "@/lib/api";
import type { BizClient } from "@/lib/types";

export function useClientsPage() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");

  /** 分页查询客户列表，支持关键词搜索 */
  const list = usePagedList(
    (page, size) => api.listClients(page, size, search || undefined),
    { enabled: ready },
  );

  const { requestConfirm, confirmDialog } = useConfirmAction();

  const handleSearch = (q: string) => {
    setSearch(q);
  };

  const handleDelete = useCallback(
    (client: BizClient) => {
      requestConfirm({
        title: "删除客户",
        description: `确定删除「${client.name}」？`,
        onConfirm: async () => {
          await api.deleteClient(client.id);
          list.reload();
        },
      });
    },
    [requestConfirm, list],
  );

  return { ready, search, onSearch: handleSearch, list, onDelete: handleDelete, confirmDialog };
}

export type ClientsPageVm = ReturnType<typeof useClientsPage>;
