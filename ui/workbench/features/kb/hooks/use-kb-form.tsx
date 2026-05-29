"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import {
  DEFAULT_CHUNK_OVERLAP,
  DEFAULT_CHUNK_SIZE,
  DEFAULT_RERANK_CANDIDATE_K,
} from "@/features/kb/lib/kb-page-shared";
import type { KnowledgeBase, ModelConfig } from "@/lib/types";
import type { KbListSlice } from "@/features/kb/hooks/use-kb-list";

type ModelsSlice = {
  embeddingModels: ModelConfig[];
  textEmbeddingModels: ModelConfig[];
  rerankModels: ModelConfig[];
};

export function useKbForm(listSlice: KbListSlice, models: ModelsSlice) {
  const router = useRouter();
  const { list, reloadQuota } = listSlice;
  const { embeddingModels, textEmbeddingModels, rerankModels } = models;
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<KnowledgeBase | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [chunkSize, setChunkSize] = useState(DEFAULT_CHUNK_SIZE);
  const [chunkOverlap, setChunkOverlap] = useState(DEFAULT_CHUNK_OVERLAP);
  const [embeddingModelId, setEmbeddingModelId] = useState("");
  const [visualModelId, setVisualModelId] = useState("");
  const [rerankModelId, setRerankModelId] = useState("");
  const [rerankCandidateK, setRerankCandidateK] = useState(DEFAULT_RERANK_CANDIDATE_K);
  const [retrievalMode, setRetrievalMode] = useState<"vector" | "hybrid">("vector");
  const [hybridAlpha, setHybridAlpha] = useState(0.5);
  const [saveError, setSaveError] = useState("");

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
