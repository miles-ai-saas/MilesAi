"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useKbMeta } from "@/hooks/use-kb-meta";
import { isDocumentProcessing } from "@/lib/document-status";
import { type KbDetailAlertState, type KbDetailTabKey, type KbDocFilter, type KbSearchHit, matchKbDocFilter } from "@/lib/kb-detail-shared";
import type { Document, KnowledgeBase, KbQuota } from "@/lib/types";

export function useKbDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { ready } = useRequireAuth();
  const [tab, setTab] = useState<KbDetailTabKey>("documents");
  const [kb, setKb] = useState<KnowledgeBase | null>(null);
  const kbMeta = useKbMeta(ready && !!id);
  const [quota, setQuota] = useState<KbQuota | null>(null);
  const [quotaLoading, setQuotaLoading] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editChunkSize, setEditChunkSize] = useState(500);
  const [editChunkOverlap, setEditChunkOverlap] = useState(50);
  const [editRetrievalMode, setEditRetrievalMode] = useState<"vector" | "hybrid">("vector");
  const [editHybridAlpha, setEditHybridAlpha] = useState(0.5);
  const [uploading, setUploading] = useState(false);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [chunksDoc, setChunksDoc] = useState<Document | null>(null);
  const [docFilter, setDocFilter] = useState<KbDocFilter>("all");
  const [expandedFailId, setExpandedFailId] = useState<string | null>(null);
  const [searchQ, setSearchQ] = useState("");
  const [searchTopK, setSearchTopK] = useState(5);
  const [searchMode, setSearchMode] = useState<"default" | "vector" | "hybrid">("default");
  const [searchMediaTypes, setSearchMediaTypes] = useState<string[]>([]);
  const [searchQueryDocId, setSearchQueryDocId] = useState("");
  const [searchVisual, setSearchVisual] = useState(false);
  const [searching, setSearching] = useState(false);
  const [searchResultMode, setSearchResultMode] = useState("");
  const [searchHits, setSearchHits] = useState<KbSearchHit[]>([]);
  const [alert, setAlert] = useState<KbDetailAlertState>(null);
  const [docsRefreshing, setDocsRefreshing] = useState(false);
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const docs = usePagedList(
    useCallback((p, s) => api.listDocuments(id, p, s), [id]),
    {
      enabled: ready && !!id,
      resetKey: id,
    },
  );

  const logs = usePagedList(
    useCallback((p, s) => api.listKbSearchLogs(id, p, s), [id]),
    { enabled: ready && !!id && tab === "logs", resetKey: `${id}-${tab}` },
  );

  const filteredDocs = useMemo(() => docs.items.filter((d) => matchKbDocFilter(d.status, docFilter)), [docs.items, docFilter]);

  const hasProcessing = docs.items.some((d) => isDocumentProcessing(d.status));

  const reloadQuota = useCallback(() => {
    return api
      .getKbQuota()
      .then(setQuota)
      .catch(() => setQuota(null))
      .finally(() => setQuotaLoading(false));
  }, []);

  const reloadKb = useCallback(() => {
    if (!id) return;
    return api.getKb(id).then(setKb);
  }, [id]);

  useEffect(() => {
    if (!ready || !id) return;
    setQuotaLoading(true);
    Promise.all([reloadKb(), reloadQuota()]).catch((e) => setAlert({ tone: "error", message: e instanceof Error ? e.message : "加载失败" }));
  }, [ready, id, reloadKb, reloadQuota]);

  const onRefreshDocuments = async () => {
    setDocsRefreshing(true);
    try {
      await Promise.all([docs.reload(), reloadQuota()]);
    } finally {
      setDocsRefreshing(false);
    }
  };

  const openSettings = () => {
    if (!kb) return;
    setEditName(kb.name);
    setEditDesc(kb.description ?? "");
    setEditChunkSize(kb.chunk_size ?? 500);
    setEditChunkOverlap(kb.chunk_overlap ?? 50);
    setEditRetrievalMode(kb.retrieval_mode === "hybrid" ? "hybrid" : "vector");
    setEditHybridAlpha(kb.hybrid_alpha ?? 0.5);
    setSettingsOpen(true);
  };

  const onSaveSettings = async () => {
    if (!kb) return;
    const updated = await api.updateKb(kb.id, {
      name: editName.trim() || kb.name,
      description: editDesc || null,
      chunk_size: editChunkSize,
      chunk_overlap: editChunkOverlap,
      retrieval_mode: editRetrievalMode,
      hybrid_alpha: editHybridAlpha,
    });
    setKb(updated);
    setSettingsOpen(false);
    setAlert({
      tone: "info",
      message: "设置已保存；分片参数仅影响之后上传或重试的文档。",
    });
  };

  const onDeleteKb = () => {
    if (!kb) return;
    requestConfirm({
      title: "删除知识库",
      description: "此操作不可撤销。",
      message: (
        <>
          确定删除知识库 <span className="font-medium">{kb.name}</span>
          ？将删除其下全部文档与向量数据。
        </>
      ),
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deleteKb(kb.id);
        router.push("/workbench/kb");
      },
    });
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

  const imageVideoDocs = useMemo(
    () => docs.items.filter((d) => d.status === "ready" && (/^image\//.test(d.mime_type) || /^video\//.test(d.mime_type))),
    [docs.items],
  );

  const imageDocs = useMemo(() => docs.items.filter((d) => d.status === "ready" && /^image\//.test(d.mime_type)), [docs.items]);

  const onSearch = async () => {
    const q = searchQ.trim();
    if (searchVisual ? !q && !searchQueryDocId : !q && !searchQueryDocId) return;
    setSearching(true);
    setAlert(null);
    try {
      const res = await api.searchKb(id, q, {
        mode: searchMode,
        top_k: searchTopK,
        ...(searchMediaTypes.length ? { media_types: searchMediaTypes as ("text" | "image" | "audio" | "video")[] } : {}),
        ...(searchQueryDocId ? { query_document_id: searchQueryDocId } : {}),
        ...(searchVisual ? { visual_search: true } : {}),
      });
      setSearchResultMode(res.mode);
      setSearchHits(res.hits);
      if (tab === "logs") await logs.reload();
    } catch (err) {
      setAlert({ tone: "error", message: err instanceof Error ? err.message : "检索失败" });
    } finally {
      setSearching(false);
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
    id,
    router,
    ready,
    tab,
    setTab,
    kb,
    kbMeta,
    quota,
    quotaLoading,
    settingsOpen,
    setSettingsOpen,
    editName,
    setEditName,
    editDesc,
    setEditDesc,
    editChunkSize,
    setEditChunkSize,
    editChunkOverlap,
    setEditChunkOverlap,
    editRetrievalMode,
    setEditRetrievalMode,
    editHybridAlpha,
    setEditHybridAlpha,
    uploading,
    retryingId,
    chunksDoc,
    setChunksDoc,
    docFilter,
    setDocFilter,
    expandedFailId,
    setExpandedFailId,
    searchQ,
    setSearchQ,
    searchTopK,
    setSearchTopK,
    searchMode,
    setSearchMode,
    searchMediaTypes,
    setSearchMediaTypes,
    searchQueryDocId,
    setSearchQueryDocId,
    searchVisual,
    setSearchVisual,
    searching,
    searchResultMode,
    searchHits,
    alert,
    setAlert,
    docsRefreshing,
    confirmDialog,
    docs,
    logs,
    filteredDocs,
    hasProcessing,
    imageVideoDocs,
    imageDocs,
    openSettings,
    onRefreshDocuments,
    onSaveSettings,
    onDeleteKb,
    onUploadFiles,
    onRetry,
    onSearch,
    onRequestDeleteDoc,
  };
}

export type KbDetailPageVm = ReturnType<typeof useKbDetailPage>;
