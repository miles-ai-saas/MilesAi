"use client";

import { useState } from "react";
import { useToolsCatalog } from "@/hooks/use-tools-catalog";
import { useToolsFormDialog } from "@/hooks/use-tools-form-dialog";
import { useToolsOverlays } from "@/hooks/use-tools-overlays";
import { useToolsMeta } from "@/hooks/use-tools-meta";
import { useRequireAuth } from "@/lib/auth-store";
import { TOOLS_MAIN_TABS, TOOLS_PAGE_DESC } from "@/lib/tool-page-shared";
import { toolKindTabs, type ToolPageTab, type ToolSourceTab } from "@/lib/tool-labels";

export function useToolsPage() {
  const { ready } = useRequireAuth();
  const toolsMeta = useToolsMeta(ready);
  const [pageTab, setPageTab] = useState<ToolPageTab>("catalog");
  const [sourceTab, setSourceTab] = useState<ToolSourceTab>("");
  const [search, setSearch] = useState("");
  const [tagFilterIds, setTagFilterIds] = useState<string[]>([]);
  const [tagManageOpen, setTagManageOpen] = useState(false);

  const switchPageTab = (tab: ToolPageTab) => {
    setPageTab(tab);
    setSearch("");
  };

  const catalog = useToolsCatalog({ ready, pageTab, search, sourceTab, tagFilterIds });
  const dialog = useToolsFormDialog({ reloadCatalog: catalog.reloadCatalog });
  const overlays = useToolsOverlays({ reloadCatalog: catalog.reloadCatalog });

  const layoutCommon = {
    title: "工具",
    description: TOOLS_PAGE_DESC,
    tabs: TOOLS_MAIN_TABS,
    activeTab: pageTab,
    onTabChange: (k: string) => switchPageTab(k as ToolPageTab),
  };

  return {
    layoutCommon,
    toolsMeta,
    pageTab,
    switchPageTab,
    sourceTab,
    setSourceTab,
    search,
    setSearch,
    tagFilterIds,
    setTagFilterIds,
    tagManageOpen,
    setTagManageOpen,
    kindTabs: toolKindTabs(toolsMeta),
    ...catalog,
    ...dialog,
    ...overlays,
  };
}

export type ToolsPageVm = ReturnType<typeof useToolsPage>;
