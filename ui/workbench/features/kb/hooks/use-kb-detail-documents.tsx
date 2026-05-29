"use client";

import { useCallback, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { isDocumentProcessing } from "@/lib/document-status";
import { type KbDetailTabKey, type KbDocFilter, matchKbDocFilter } from "@/features/kb/lib/kb-detail-shared";
import type { Document } from "@/lib/types";
import type { KbDetailAlertState } from "@/features/kb/lib/kb-detail-shared";

type CoreSlice = {
  id: string;
  ready: boolean;
  setAlert: (alert: KbDetailAlertState) => void;
  reloadQuota: () => Promise<unknown>;
  setTab: (tab: KbDetailTabKey) => void;
  requestConfirm: ReturnType<typeof useConfirmAction>["requestConfirm"];
};

export function useKbDetailDocuments({ id, ready, setAlert, reloadQuota, setTab, requestConfirm }: CoreSlice) {
  const [uploading, setUploading] = useState(false);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [chunksDoc, setChunksDoc] = useState<Document | null>(null);
  const [docFilter, setDocFilter] = useState<KbDocFilter>("all");
  const [expandedFailId, setExpandedFailId] = useState<string | null>(null);
  const [docsRefreshing, setDocsRefreshing] = useState(false);

  const docs = usePagedList(
    useCallback((p, s) => api.listDocuments(id, p, s), [id]),
    {
      enabled: ready && !!id,
      resetKey: id,
    },
  );

  const filteredDocs = useMemo(() => docs.items.filter((d) => matchKbDocFilter(d.status, docFilter)), [docs.items, docFilter]);
  const hasProcessing = docs.items.some((d) => isDocumentProcessing(d.status));

  const onRefreshDocuments = async () => {
    setDocsRefreshing(true);
    try {
      await Promise.all([docs.reload(), reloadQuota()]);
    } finally {
      setDocsRefreshing(false);
    }
  };

  const onUploadFiles = async (files: File[]) => {
    if (!files.length) return;
    setUploading(true);
    setAlert(null);
    try {
      if (files.length === 1) {
        await api.uploadDocument(id, files[0]);
        setAlert({
          tone: "success",
          message: `「${files[0].name}」已上传，正在后台解析入库。`,
        });
      } else {
        const uploaded = await api.uploadDocumentsBatch(id, files);
        setAlert({
          tone: "success",
          message: `已提交 ${uploaded.length} 个文件入库（共选择 ${files.length} 个）。`,
        });
      }
      await Promise.all([docs.reload(), reloadQuota()]);
      setTab("documents");
    } catch (err) {
      setAlert({ tone: "error", message: err instanceof Error ? err.message : "上传失败" });
    } finally {
      setUploading(false);
    }
  };

  const onRetry = async (docId: string) => {
    setRetryingId(docId);
    setAlert(null);
    try {
      await api.retryDocument(id, docId);
      await docs.reload();
      setAlert({ tone: "success", message: "已重新提交入库任务。" });
    } catch (err) {
      setAlert({ tone: "error", message: err instanceof Error ? err.message : "重试失败" });
    } finally {
      setRetryingId(null);
    }
  };

  const onRequestDeleteDoc = (doc: Document) => {
    requestConfirm({
      title: "删除文档",
      description: "此操作不可撤销，向量索引将一并清除。",
      message: (
        <>
          确定删除文档 <span className="font-medium break-all">{doc.filename}</span>？
        </>
      ),
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deleteDocument(id, doc.id);
        await Promise.all([docs.reload(), reloadQuota()]);
        setAlert({ tone: "success", message: "文档已删除。" });
      },
    });
  };

  return {
    docs,
    filteredDocs,
    hasProcessing,
    uploading,
    retryingId,
    chunksDoc,
    setChunksDoc,
    docFilter,
    setDocFilter,
    expandedFailId,
    setExpandedFailId,
    docsRefreshing,
    onRefreshDocuments,
    onUploadFiles,
    onRetry,
    onRequestDeleteDoc,
  };
}

export type KbDetailDocumentsSlice = ReturnType<typeof useKbDetailDocuments>;
