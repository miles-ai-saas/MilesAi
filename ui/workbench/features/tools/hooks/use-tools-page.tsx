"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useToolsCatalog } from "@/features/tools/hooks/use-tools-catalog";
import { useToolsFormDialog } from "@/features/tools/hooks/use-tools-form-dialog";
import { useToolsMeta } from "@/features/tools/hooks/use-tools-meta";
import { useRequireAuth } from "@/lib/auth-store";
import { TOOL_PAGE_TABS, toolKindTabs, type ToolPageTab, type ToolSourceTab } from "@/features/tools/lib/tool-labels";
import type { ToolCatalogItem } from "@/lib/types";

const TOOLS_MAIN_TABS = TOOL_PAGE_TABS.map((t) => ({ key: t.key, label: t.label }));

const TOOLS_PAGE_DESC =
  "平台内置与自定义 HTTP / Python 脚本工具；供技能包引用与智能体 function calling。外部 MCP 服务请前往 MCP 工作台。";

function useToolsOverlays({ reloadCatalog }: { reloadCatalog: () => Promise<void> }) {
  const [testOpen, setTestOpen] = useState(false);
  const [testTool, setTestTool] = useState<ToolCatalogItem | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailTool, setDetailTool] = useState<ToolCatalogItem | null>(null);
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const openDetail = (item: ToolCatalogItem) => {
    setDetailTool(item);
    setDetailOpen(true);
  };

  const openTest = (tool: ToolCatalogItem) => {
    setTestTool(tool);
    setTestOpen(true);
  };

  const runTest = async (params: Record<string, unknown>, confirmed: boolean) => {
    if (!testTool) return "";
    const res = await api.invokeTool(testTool.slug, params, testTool.tool_id || undefined, confirmed);
    if (res.status === "confirmation_required" && res.pending) {
      return `__CONFIRM__:工具「${res.pending.name}」需要确认。\n参数：${JSON.stringify(res.pending.params, null, 2)}`;
    }
    return JSON.stringify(res.output, null, 2);
  };

  const onDelete = (item: ToolCatalogItem) => {
    if (!item.tool_id) return;
    requestConfirm({
      title: "删除工具",
      message: (
        <>
          确定删除工具 <span className="font-medium">{item.name}</span>？
        </>
      ),
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deleteCustomTool(item.tool_id!);
        await reloadCatalog();
      },
    });
  };

  return {
    testOpen,
    setTestOpen,
    testTool,
    detailOpen,
    setDetailOpen,
    detailTool,
    confirmDialog,
    openDetail,
    openTest,
    runTest,
    onDelete,
  };
}

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
