"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useKbMeta } from "@/hooks/use-kb-meta";
import { filterBySearch } from "@/lib/filter-search";
import {
  DEFAULT_CHUNK_OVERLAP,
  DEFAULT_CHUNK_SIZE,
  DEFAULT_RERANK_CANDIDATE_K,
  isClipModel,
} from "@/lib/kb-page-shared";
import type { KnowledgeBase, KbQuota, ModelConfig } from "@/lib/types";

export function useKbPage() {
  const router = useRouter();
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<KnowledgeBase | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [chunkSize, setChunkSize] = useState(DEFAULT_CHUNK_SIZE);
  const [chunkOverlap, setChunkOverlap] = useState(DEFAULT_CHUNK_OVERLAP);
  const [embeddingModels, setEmbeddingModels] = useState<ModelConfig[]>([]);
  const [rerankModels, setRerankModels] = useState<ModelConfig[]>([]);
  const [embeddingModelId, setEmbeddingModelId] = useState("");
  const [visualModelId, setVisualModelId] = useState("");
  const [rerankModelId, setRerankModelId] = useState("");
  const [rerankCandidateK, setRerankCandidateK] = useState(DEFAULT_RERANK_CANDIDATE_K);
  const [retrievalMode, setRetrievalMode] = useState<"vector" | "hybrid">("vector");
  const [hybridAlpha, setHybridAlpha] = useState(0.5);
  const kbMeta = useKbMeta(ready);
  const [quota, setQuota] = useState<KbQuota | null>(null);
  const [quotaLoading, setQuotaLoading] = useState(true);
  const [saveError, setSaveError] = useState("");

  const list = usePagedList(useCallback((p, s) => api.listKbs(p, s), []), { enabled: ready });
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const reloadQuota = useCallback(() => {
    if (!ready) return Promise.resolve();
    setQuotaLoading(true);
    return api
      .getKbQuota()
      .then(setQuota)
      .catch(() => setQuota(null))
      .finally(() => setQuotaLoading(false));
  }, [ready]);

  useEffect(() => {
    void reloadQuota();
  }, [reloadQuota]);

  useEffect(() => {
    if (!ready) return;
    void api
      .listModelConfigs({ model_type: "embedding" })
      .then((items) => {
        setEmbeddingModels(items);
        const textModels = items.filter((m) => m.extra?.invoke_mode !== "clip");
        setEmbeddingModelId((prev) => prev || textModels[0]?.id || items[0]?.id || "");
      })
      .catch(() => {});
    void api
      .listModelConfigs({ model_type: "rerank" })
      .then(setRerankModels)
      .catch(() => {});
  }, [ready]);

  const textEmbeddingModels = useMemo(() => embeddingModels.filter((m) => !isClipModel(m)), [embeddingModels]);
  const clipModels = useMemo(() => embeddingModels.filter((m) => isClipModel(m)), [embeddingModels]);
  const filtered = useMemo(() => filterBySearch(list.items, search, (kb) => `${kb.name} ${kb.description ?? ""}`), [list.items, search]);

  const openCreate = () => {
    setEditing(null);
    setName("");
    setDescription("");
    setChunkSize(DEFAULT_CHUNK_SIZE);
    setChunkOverlap(DEFAULT_CHUNK_OVERLAP);
    setEmbeddingModelId(textEmbeddingModels[0]?.id || embeddingModels[0]?.id || "");
    setVisualModelId("");
    setRerankModelId("");
    setRerankCandidateK(DEFAULT_RERANK_CANDIDATE_K);
    setRetrievalMode("vector");
    setHybridAlpha(0.5);
    setDialogOpen(true);
  };

  const openEdit = (kb: KnowledgeBase) => {
    setEditing(kb);
    setName(kb.name);
    setDescription(kb.description ?? "");
    setChunkSize(kb.chunk_size ?? DEFAULT_CHUNK_SIZE);
    setChunkOverlap(kb.chunk_overlap ?? DEFAULT_CHUNK_OVERLAP);
    setRetrievalMode(kb.retrieval_mode === "hybrid" ? "hybrid" : "vector");
    setHybridAlpha(kb.hybrid_alpha ?? 0.5);
    setRerankModelId(kb.rerank_model_config_id ?? "");
    setVisualModelId(kb.visual_embedding_model_config_id ?? "");
    setRerankCandidateK(kb.rerank_candidate_k ?? DEFAULT_RERANK_CANDIDATE_K);
    setDialogOpen(true);
  };

  const onSave = async () => {
    setSaveError("");
    try {
      if (editing) {
        await api.updateKb(editing.id, {
          name: name.trim() || editing.name,
          description: description || null,
          chunk_size: chunkSize,
          chunk_overlap: chunkOverlap,
          retrieval_mode: retrievalMode,
          hybrid_alpha: hybridAlpha,
          rerank_model_config_id: rerankModelId || null,
          rerank_candidate_k: rerankModelId ? rerankCandidateK : undefined,
          visual_embedding_model_config_id: visualModelId || null,
        });
      } else {
        await api.createKb({
          name: name.trim() || `知识库 ${list.total + 1}`,
          description: description || undefined,
          embedding_model_config_id: embeddingModelId || undefined,
          visual_embedding_model_config_id: visualModelId || null,
          chunk_size: chunkSize,
          chunk_overlap: chunkOverlap,
          retrieval_mode: retrievalMode,
          hybrid_alpha: hybridAlpha,
          rerank_model_config_id: rerankModelId || null,
          rerank_candidate_k: rerankModelId ? rerankCandidateK : undefined,
        });
      }
      setDialogOpen(false);
      await Promise.all([list.reload(), reloadQuota()]);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "保存失败");
    }
  };

  const onDelete = (kb: KnowledgeBase) => {
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
        await Promise.all([list.reload(), reloadQuota()]);
      },
    });
  };

  const closeDialog = () => {
    setDialogOpen(false);
    setSaveError("");
  };

  return {
    router,
    kbMeta,
    search,
    setSearch,
    list,
    quota,
    quotaLoading,
    filtered,
    saveError,
    setSaveError,
    listError: list.error ?? "",
    dialogOpen,
    editing,
    name,
    setName,
    description,
    setDescription,
    chunkSize,
    setChunkSize,
    chunkOverlap,
    setChunkOverlap,
    embeddingModelId,
    setEmbeddingModelId,
    visualModelId,
    setVisualModelId,
    rerankModelId,
    setRerankModelId,
    rerankCandidateK,
    setRerankCandidateK,
    retrievalMode,
    setRetrievalMode,
    hybridAlpha,
    setHybridAlpha,
    textEmbeddingModels,
    clipModels,
    rerankModels,
    confirmDialog,
    openCreate,
    openEdit,
    onSave,
    onDelete,
    closeDialog,
    clearListError: list.clearError,
  };
}

export type KbPageVm = ReturnType<typeof useKbPage>;
