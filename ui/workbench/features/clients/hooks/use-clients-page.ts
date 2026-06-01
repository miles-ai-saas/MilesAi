"use client";

/** 客户列表页 VM——分页查询、关键词搜索、确认删除、新建/详情弹窗。 */

import { useCallback, useState } from "react";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useRequireAuth } from "@/lib/auth-store";
import { api } from "@/lib/api";
import { useBizDetailNavigation, useBizLegacyDetailRedirect } from "@/features/business/lib/use-biz-detail-tab";
import { EMPTY_CLIENT_FORM, type ClientFormValues } from "@/features/clients/lib/client-form-options";
import type { BizClient } from "@/lib/types";

export function useClientsPage() {
  const { ready } = useRequireAuth();
  useBizLegacyDetailRedirect("/business/clients");
  const { openDetail } = useBizDetailNavigation("/business/clients");
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<ClientFormValues>(EMPTY_CLIENT_FORM);
  const [saving, setSaving] = useState(false);

  const filterKey = search;
  const list = usePagedList(
    (page, size) => api.listClients(page, size, search || undefined),
    { enabled: ready, resetKey: filterKey },
  );

  const { requestConfirm, confirmDialog } = useConfirmAction();

  const openCreate = useCallback(() => {
    setCreateForm(EMPTY_CLIENT_FORM);
    setCreateOpen(true);
  }, []);

  const handleCreateSave = useCallback(async () => {
    if (!createForm.name.trim()) return;
    setSaving(true);
    try {
      const client = await api.createClient({
        name: createForm.name.trim(),
        short_name: createForm.short_name.trim() || undefined,
        industry: createForm.industry || undefined,
        confidentiality_level: createForm.confidentiality_level,
        address: createForm.address.trim() || undefined,
        remark: createForm.remark.trim() || undefined,
      });
      setCreateOpen(false);
      await list.reload();
      openDetail(client.id);
    } finally {
      setSaving(false);
    }
  }, [createForm, list, openDetail]);

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

  const clearFilters = useCallback(() => setSearch(""), []);

  return {
    ready,
    search,
    onSearch: setSearch,
    clearFilters,
    hasActiveFilters: Boolean(search),
    list,
    onDelete: handleDelete,
    confirmDialog,
    createOpen,
    setCreateOpen,
    createForm,
    setCreateForm,
    saving,
    openCreate,
    handleCreateSave,
    openDetail,
  };
}

export type ClientsPageVm = ReturnType<typeof useClientsPage>;
