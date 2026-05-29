"use client";

import { useState } from "react";
import { type KbDetailTabKey } from "@/features/kb/lib/kb-detail-shared";
import { useKbDetailCore } from "@/features/kb/hooks/use-kb-detail-core";
import { useKbDetailDocuments } from "@/features/kb/hooks/use-kb-detail-documents";
import { useKbDetailSearch } from "@/features/kb/hooks/use-kb-detail-search";

export function useKbDetailPage() {
  const [tab, setTab] = useState<KbDetailTabKey>("documents");
  const core = useKbDetailCore();
  const documents = useKbDetailDocuments({
    id: core.id,
    ready: core.ready,
    setAlert: core.setAlert,
    reloadQuota: core.reloadQuota,
    setTab,
    requestConfirm: core.requestConfirm,
  });
  const search = useKbDetailSearch({
    id: core.id,
    ready: core.ready,
    tab,
    setAlert: core.setAlert,
    docItems: documents.docs.items,
  });

  return {
    ...core,
    tab,
    setTab,
    ...documents,
    ...search,
  };
}

export type KbDetailPageVm = ReturnType<typeof useKbDetailPage>;
