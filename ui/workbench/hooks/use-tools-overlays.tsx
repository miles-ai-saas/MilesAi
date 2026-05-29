"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import type { ToolCatalogItem } from "@/lib/types";

type Params = {
  reloadCatalog: () => Promise<void>;
};

export function useToolsOverlays({ reloadCatalog }: Params) {
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

export type ToolsOverlays = ReturnType<typeof useToolsOverlays>;
