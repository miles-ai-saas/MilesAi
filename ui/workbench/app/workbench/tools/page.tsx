"use client";

/** 工具工作台（链路 §3 + §4）：目录/调用日志 + `useToolsMeta`。 */

import { ToolsCatalogTab } from "@/components/tool/ToolsCatalogTab";
import { ToolsLogsTab } from "@/components/tool/ToolsLogsTab";
import { ToolsPageOverlays } from "@/components/tool/ToolsPageOverlays";
import { useToolsPage } from "@/hooks/use-tools-page";

export default function ToolsPage() {
  const vm = useToolsPage();
  const overlays = <ToolsPageOverlays vm={vm} />;

  if (vm.pageTab === "logs") {
    return (
      <>
        <ToolsLogsTab vm={vm} />
        {overlays}
      </>
    );
  }

  return (
    <>
      <ToolsCatalogTab vm={vm} />
      {overlays}
    </>
  );
}
