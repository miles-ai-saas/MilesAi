"use client";

import { useCallback, useState } from "react";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useRequireAuth } from "@/lib/auth-store";
import { api } from "@/lib/api";
import { useBizDetailNavigation, useBizLegacyDetailRedirect } from "@/features/business/lib/use-biz-detail-tab";
import { EMPTY_SUPPLIER_FORM, type SupplierFormValues } from "@/features/suppliers/lib/supplier-form-options";
import type { BizSupplier } from "@/lib/types";

export function useSuppliersPage() {
  const { ready } = useRequireAuth();
  useBizLegacyDetailRedirect("/business/suppliers");
  const { openDetail } = useBizDetailNavigation("/business/suppliers");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<SupplierFormValues>(EMPTY_SUPPLIER_FORM);
  const [saving, setSaving] = useState(false);

  const filterKey = `${search}|${category}|${status}`;
  const list = usePagedList(
    (page, size) => api.listSuppliers(page, size, search || undefined, category || undefined, status || undefined),
    { enabled: ready, resetKey: filterKey },
  );

  const { requestConfirm, confirmDialog } = useConfirmAction();

  const openCreate = useCallback(() => {
    setCreateForm(EMPTY_SUPPLIER_FORM);
    setCreateOpen(true);
  }, []);

  const handleCreateSave = useCallback(async () => {
    if (!createForm.name.trim()) return;
    setSaving(true);
    try {
      const supplier = await api.createSupplier({
        name: createForm.name.trim(),
        short_name: createForm.short_name.trim() || undefined,
        category: createForm.category,
        status: createForm.status,
        contact_name: createForm.contact_name.trim() || undefined,
        contact_phone: createForm.contact_phone.trim() || undefined,
        contact_email: createForm.contact_email.trim() || undefined,
        address: createForm.address.trim() || undefined,
        bank_name: createForm.bank_name.trim() || undefined,
        bank_account: createForm.bank_account.trim() || undefined,
        remark: createForm.remark.trim() || undefined,
      });
      setCreateOpen(false);
      await list.reload();
      openDetail(supplier.id);
    } finally {
      setSaving(false);
    }
  }, [createForm, list, openDetail]);

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

  const clearFilters = useCallback(() => {
    setSearch("");
    setCategory("");
    setStatus("");
  }, []);

  const hasActiveFilters = Boolean(search || category || status);

  return {
    ready,
    search,
    category,
    status,
    onSearch: setSearch,
    onCategory: setCategory,
    onStatus: setStatus,
    clearFilters,
    hasActiveFilters,
    list,
    onDelete: handleDelete,
    confirmDialog,
    openDetail,
    createOpen,
    setCreateOpen,
    createForm,
    setCreateForm,
    saving,
    openCreate,
    handleCreateSave,
  };
}

export type SuppliersPageVm = ReturnType<typeof useSuppliersPage>;
