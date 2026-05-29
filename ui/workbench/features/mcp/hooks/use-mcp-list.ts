"use client";

import { useCallback, useMemo, useState } from "react";
import { usePagedList } from "@/hooks/use-paged-list";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { filterBySearch } from "@/lib/filter-search";
import { mcpTransportFilterOptions, mcpTransportLabel, type McpTransportTab } from "@/features/mcp/lib/mcp-labels";
import { useMcpMeta } from "@/features/mcp/hooks/use-mcp-meta";
import type { McpService } from "@/lib/types";

export function useMcpList() {
  const { ready } = useRequireAuth();
  const mcpMeta = useMcpMeta(ready);
  const transportTabs = mcpTransportFilterOptions(mcpMeta);
  const [activeTab, setActiveTab] = useState<McpTransportTab>("");
  const [search, setSearch] = useState("");
  const [msg, setMsg] = useState("");

  const list = usePagedList(useCallback((p, s) => api.listMcpServices(p, s, activeTab || undefined), [activeTab]), {
    enabled: ready,
    resetKey: activeTab,
  });

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (s) => `${s.name} ${s.description ?? ""} ${s.endpoint_url} ${mcpTransportLabel(s.transport, mcpMeta)}`),
    [list.items, search, mcpMeta],
  );

  const pageStats = useMemo(() => {
    let synced = 0;
    let warn = 0;
    let tools = 0;
    for (const s of list.items) {
      if (s.sync_error) warn += 1;
      else if (s.last_sync_at && (s.tools_cache?.length ?? 0) > 0) synced += 1;
      tools += s.tools_cache?.length ?? 0;
    }
    return { synced, warn, tools };
  }, [list.items]);

  const onTabChange = (key: string) => {
    setActiveTab(key as McpTransportTab);
    setSearch("");
  };

  const activeTabLabel = transportTabs.find((t) => t.value === activeTab)?.label ?? "全部";
  const layoutTabs = useMemo(() => transportTabs.map((t) => ({ key: t.value, label: t.label })), [transportTabs]);

  return {
    mcpMeta,
    activeTab,
    onTabChange,
    search,
    setSearch,
    msg,
    setMsg,
    list,
    filtered,
    pageStats,
    activeTabLabel,
    layoutTabs,
  };
}

export type McpListSlice = ReturnType<typeof useMcpList>;

export function useMcpViewing(listItems: McpService[]) {
  const [viewing, setViewing] = useState<McpService | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const viewingLive = useMemo(() => {
    if (!viewing) return null;
    return listItems.find((s) => s.id === viewing.id) ?? viewing;
  }, [viewing, listItems]);

  const openDetail = (s: McpService) => {
    setViewing(s);
    setDetailOpen(true);
  };

  return { viewing, setViewing, detailOpen, setDetailOpen, viewingLive, openDetail };
}
