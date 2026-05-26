"use client";

/**
 * 资源列表「分类」Tab（链路 §3）：`api.listCategories(domain)` → 注入 `ResourceListLayout.tabs`。
 * `activeCategoryId` 传给 `api.list*` 的 category 筛选参数。
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { CategoryDomain, SysCategory } from "@/lib/types";
import type { ResourceTab } from "@/components/resource/ResourceListLayout";

export function useCategoryTabs(domain: CategoryDomain) {
  const [categories, setCategories] = useState<SysCategory[]>([]);
  const [activeId, setActiveId] = useState("");
  const reload = useCallback(async () => {
    const rows = await api.listCategories(domain);
    setCategories(rows);
  }, [domain]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const tabs: ResourceTab[] = useMemo(
    () => [
      { key: "", label: "全部" },
      ...categories.map((c) => ({ key: c.id, label: c.name })),
    ],
    [categories],
  );

  const activeCategoryId = activeId || undefined;

  return {
    categories,
    tabs,
    activeId,
    setActiveId,
    activeCategoryId,
    reload,
  };
}
