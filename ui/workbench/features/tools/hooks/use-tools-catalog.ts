"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePagedList } from "@/hooks/use-paged-list";
import { api } from "@/lib/api";
import { filterBySearch } from "@/lib/filter-search";
import type { ToolPageTab, ToolSourceTab } from "@/features/tools/lib/tool-labels";
import type { ToolCatalogItem } from "@/lib/types";

type Params = {
  ready: boolean;
  pageTab: ToolPageTab;
  search: string;
  sourceTab: ToolSourceTab;
  tagFilterIds: string[];
};

export function useToolsCatalog({ ready, pageTab, search, sourceTab, tagFilterIds }: Params) {
  const [catalog, setCatalog] = useState<ToolCatalogItem[]>([]);
  const [loading, setLoading] = useState(false);

  const logList = usePagedList(useCallback((p, s) => api.listToolInvocationLogs(p, s), []), {
    enabled: ready && pageTab === "logs",
  });

  const reloadCatalog = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await api.listToolCatalog(sourceTab || undefined, undefined, tagFilterIds.length ? tagFilterIds : undefined);
      setCatalog(rows);
    } finally {
      setLoading(false);
    }
  }, [sourceTab, tagFilterIds]);

  useEffect(() => {
    if (!ready || pageTab !== "catalog") return;
    void reloadCatalog();
  }, [ready, pageTab, reloadCatalog]);

  const filtered = useMemo(
    () => filterBySearch(catalog, search, (t) => `${t.name} ${t.slug} ${t.description ?? ""} ${t.source}`),
    [catalog, search],
  );

  const filteredLogs = useMemo(
    () =>
      filterBySearch(logList.items, search, (l) => `${l.tool_slug} ${l.status} ${l.source} ${l.invoke_source} ${l.error_message ?? ""}`),
    [logList.items, search],
  );

  const catalogStats = useMemo(() => {
    let builtin = 0;
    let custom = 0;
    for (const t of catalog) {
      if (t.source === "builtin") builtin += 1;
      else if (t.source === "custom") custom += 1;
    }
    return { total: catalog.length, builtin, custom };
  }, [catalog]);

  return {
    catalog,
    loading,
    logList,
    filtered,
    filteredLogs,
    catalogStats,
    reloadCatalog,
  };
}

export type ToolsCatalogState = ReturnType<typeof useToolsCatalog>;
