"use client";

import { useCallback, useEffect, useState } from "react";
import { adminApi, type AdminMarketplaceCategory } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export function useMarketplaceCategoriesPage() {
  const ready = useRequireAdmin();
  const [items, setItems] = useState<AdminMarketplaceCategory[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<AdminMarketplaceCategory | null>(null);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [sortOrder, setSortOrder] = useState(0);
  const [msg, setMsg] = useState("");

  const reload = useCallback(async () => {
    setItems(await adminApi.listMarketplaceCategories());
  }, []);

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

  const openEdit = (row: AdminMarketplaceCategory) => {
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
        await adminApi.updateMarketplaceCategory(editing.id, {
          name: name.trim(),
          slug: slug.trim() || undefined,
          sort_order: sortOrder,
        });
      } else {
        await adminApi.createMarketplaceCategory({
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

  const onDelete = async (row: AdminMarketplaceCategory) => {
    if (!confirm(`确定删除分类「${row.name}」？`)) return;
    try {
      await adminApi.deleteMarketplaceCategory(row.id);
      await reload();
    } catch (e) {
      alert(e instanceof Error ? e.message : "删除失败");
    }
  };

  return {
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

export type MarketplaceCategoriesPageVm = ReturnType<typeof useMarketplaceCategoriesPage>;
