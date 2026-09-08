"use client";

import { useCallback, useEffect, useState } from "react";
import { adminApi, type AdminSysCategory } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";
import type { SysCategoryDomainKey } from "@/features/sys-categories/lib/sys-categories-page-shared";

export function useSysCategoriesPage() {
  const ready = useRequireAdmin();
  const [domain, setDomain] = useState<SysCategoryDomainKey>("agent");
  const [items, setItems] = useState<AdminSysCategory[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<AdminSysCategory | null>(null);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [sortOrder, setSortOrder] = useState(0);
  const [msg, setMsg] = useState("");

  const reload = useCallback(async () => {
    setItems(await adminApi.listSysCategories(domain));
  }, [domain]);

  useEffect(() => {
    if (!ready) return;
    void reload();
  }, [ready, reload]);

  const openCreate = () => {
    setEditing(null);
    setName("");
    setSlug("");
    setSortOrder((items.length + 1) * 10);
    setMsg("");
    setDialogOpen(true);
  };

  const openEdit = (row: AdminSysCategory) => {
    setEditing(row);
    setName(row.name);
    setSlug(row.slug);
    setSortOrder(row.sort_order);
    setMsg("");
    setDialogOpen(true);
  };

  const onSave = async () => {
    if (!name.trim()) return;
    setMsg("");
    try {
      if (editing) {
        await adminApi.updateSysCategory(editing.id, {
          name: name.trim(),
          slug: slug.trim() || undefined,
          sort_order: sortOrder,
        });
      } else {
        await adminApi.createSysCategory(domain, {
          name: name.trim(),
          slug: slug.trim() || undefined,
          sort_order: sortOrder,
        });
      }
      setDialogOpen(false);
      await reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "保存失败");
    }
  };

  const onDelete = async (row: AdminSysCategory) => {
    if (!confirm(`确定删除分类「${row.name}」？全租户工作台将不可再选此项。`)) return;
    try {
      await adminApi.deleteSysCategory(row.id);
      await reload();
    } catch (e) {
      alert(e instanceof Error ? e.message : "删除失败");
    }
  };

  return {
    domain,
    setDomain,
    items,
    dialogOpen,
    setDialogOpen,
    editing,
    name,
    setName,
    slug,
    setSlug,
    sortOrder,
    setSortOrder,
    msg,
    openCreate,
    openEdit,
    onSave,
    onDelete,
  };
}

export type SysCategoriesPageVm = ReturnType<typeof useSysCategoriesPage>;
