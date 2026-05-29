"use client";

/** 知识库列表（链路 §3 + §8）；详情与文档入库见 kb/[id]。 */

import { KbCatalogView } from "@/components/kb/KbCatalogView";
import { KbFormDialog } from "@/components/kb/KbFormDialog";
import { KbPageAlerts } from "@/components/kb/KbPageAlerts";
import { useKbPage } from "@/hooks/use-kb-page";

export default function KbPage() {
  const vm = useKbPage();
  return (
    <>
      <KbPageAlerts vm={vm} />
      <KbCatalogView vm={vm} />
      <KbFormDialog vm={vm} />
      {vm.confirmDialog}
    </>
  );
}
