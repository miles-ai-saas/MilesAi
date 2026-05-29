"use client";

import { useState } from "react";
import { isDocumentProcessing } from "@/lib/document-status";
import { useKbDetailCore } from "@/features/kb/hooks/use-kb-detail-core";
import { useKbDetailDocuments } from "@/features/kb/hooks/use-kb-detail-documents";
import { useKbDetailSearch } from "@/features/kb/hooks/use-kb-detail-search";

export type KbDetailTabKey = "documents" | "search" | "logs";
export type KbDocFilter = "all" | "ready" | "processing" | "failed";

export type KbDetailAlertState = { tone: "success" | "error" | "info"; message: string } | null;

export type KbSearchHit = {
  content: string;
  score: number;
  score_vector?: number | null;
  score_keyword?: number | null;
  score_rerank?: number | null;
  filename?: string;
  vector_type?: string | null;
  mime_type?: string | null;
};

export const KB_DETAIL_TABS: { key: KbDetailTabKey; label: string }[] = [
  { key: "documents", label: "文档" },
  { key: "search", label: "检索测试" },
  { key: "logs", label: "检索记录" },
];

export const KB_DOC_FILTERS: { key: KbDocFilter; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "ready", label: "可检索" },
  { key: "processing", label: "处理中" },
  { key: "failed", label: "失败" },
];

export function matchKbDocFilter(status: string, filter: KbDocFilter): boolean {
  if (filter === "all") return true;
  if (filter === "ready") return status === "ready";
  if (filter === "processing") return isDocumentProcessing(status);
  if (filter === "failed") return status.includes("failed");
  return true;
}

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
