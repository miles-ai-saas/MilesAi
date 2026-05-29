"use client";

import { useState } from "react";
import { useToolsCatalog } from "@/features/tools/hooks/use-tools-catalog";
import { useToolsFormDialog } from "@/features/tools/hooks/use-tools-form-dialog";
import { useToolsOverlays } from "@/features/tools/hooks/use-tools-overlays";
import { useToolsMeta } from "@/features/tools/hooks/use-tools-meta";
import { useRequireAuth } from "@/lib/auth-store";
import { TOOLS_MAIN_TABS } from "@/features/tools/lib/tool-page-shared";
import { toolKindTabs, type ToolPageTab, type ToolSourceTab } from "@/features/tools/lib/tool-labels";

const TOOLS_PAGE_DESC =
  "平台内置与自定义 HTTP / Python 脚本工具；供技能包引用与智能体 function calling。外部 MCP 服务请前往 MCP 工作台。";

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
