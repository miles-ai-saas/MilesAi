"use client";

/** 知识库列表（链路 §3 + §8）；详情与文档入库见 kb/[id]。 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { CardActions } from "@/components/resource/CardActions";
import { KbPageAlert } from "@/components/kb/KbPageAlert";
import { KbQuotaBar } from "@/components/kb/KbQuotaBar";
import { filterBySearch } from "@/lib/filter-search";
import { useKbMeta } from "@/hooks/use-kb-meta";
import { retrievalModeLabel } from "@/lib/kb-labels";
import type { KnowledgeBase, KbQuota, ModelConfig } from "@/lib/types";

const DEFAULT_CHUNK_SIZE = 500;
const DEFAULT_CHUNK_OVERLAP = 50;
const DEFAULT_RERANK_CANDIDATE_K = 50;

function embeddingDimension(m: ModelConfig): number {
  const dim = m.extra?.embedding_dimension;
  return typeof dim === "number" ? dim : 0;
}

function isClipModel(m: ModelConfig): boolean {
  return m.extra?.invoke_mode === "clip";
}

export default function KbPage() {
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
    reloadQuota();
  }, [reloadQuota]);

  useEffect(() => {
    if (!ready) return;
    api
      .listModelConfigs({ model_type: "embedding" })
      .then((items) => {
        setEmbeddingModels(items);
        const textModels = items.filter((m) => m.extra?.invoke_mode !== "clip");
        setEmbeddingModelId((prev) => prev || textModels[0]?.id || items[0]?.id || "");
      })
      .catch(() => {});
    api
      .listModelConfigs({ model_type: "rerank" })
      .then(setRerankModels)
      .catch(() => {});
  }, [ready]);

  const textEmbeddingModels = useMemo(
    () => embeddingModels.filter((m) => !isClipModel(m)),
    [embeddingModels],
  );
  const clipModels = useMemo(
    () => embeddingModels.filter((m) => isClipModel(m)),
    [embeddingModels],
  );

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (kb) => `${kb.name} ${kb.description ?? ""}`),
    [list.items, search],
  );

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

  const listError = list.error ?? "";

  return (
    <>
      {(listError || saveError) && (
        <div className="resource-page-shell mb-4">
          {listError && (
            <KbPageAlert tone="error" message={listError} onDismiss={list.clearError} />
          )}
          {saveError && (
            <div className={listError ? "mt-3" : ""}>
              <KbPageAlert tone="error" message={saveError} onDismiss={() => setSaveError("")} />
            </div>
          )}
        </div>
      )}
      <ResourceListLayout
        title="知识库"
        description="管理企业知识库与文档，为智能体 RAG 检索与流程节点提供知识来源。"
        searchPlaceholder="搜索知识库名称"
        search={search}
        onSearchChange={setSearch}
        headerAction={
          <KbQuotaBar quota={quota} loading={quotaLoading} variant="inline" />
        }
        loading={list.loading}
        footer={
          !list.loading ? (
            <ResourceListFooter
              page={list.page}
              size={list.size}
              total={list.total}
              onPageChange={list.setPage}
              onSizeChange={list.setSize}
            />
          ) : null
        }
      >
        <AddResourceCard
          label="添加新知识库"
          hint="创建知识库并上传文档"
          onClick={openCreate}
        />
        {!list.loading && search.trim() && filtered.length === 0 && (
          <div className="col-span-full rounded-xl border border-dashed border-line bg-surface-muted/30 px-6 py-10 text-center">
            <p className="text-sm font-medium text-ink">没有匹配的知识库</p>
            <p className="mt-2 text-xs text-ink-faint">试试其他关键词，或清空搜索。</p>
          </div>
        )}
        {filtered.map((kb) => (
          <ResourceItemCard
            key={kb.id}
            href={`/workbench/kb/${kb.id}`}
            title={kb.name}
            description={kb.description || "管理文档、检索测试与入库状态"}
            meta={
              <span className="flex flex-wrap gap-1.5 text-ink-faint">
                <span className="rounded bg-surface-muted px-1.5 py-0.5 text-[11px]">
                  {kb.embedding_model_name ?? "向量化"}
                </span>
                <span className="rounded bg-surface-muted px-1.5 py-0.5 text-[11px]">
                  {kb.embedding_dimension} 维
                </span>
                <span className="rounded bg-brand/10 px-1.5 py-0.5 text-[11px] text-brand">
                  {retrievalModeLabel(kb.retrieval_mode, kbMeta?.retrieval_modes)}
                </span>
                {kb.rerank_model_name ? (
                  <span className="rounded bg-surface-muted px-1.5 py-0.5 text-[11px]">
                    重排 {kb.rerank_model_name}
                  </span>
                ) : null}
                <span className="text-[11px]">
                  分片 {kb.chunk_size ?? DEFAULT_CHUNK_SIZE}/{kb.chunk_overlap ?? DEFAULT_CHUNK_OVERLAP}
                </span>
              </span>
            }
            actions={
              <CardActions
                actions={[
                  {
                    label: "管理",
                    variant: "primary",
                    onClick: () => router.push(`/workbench/kb/${kb.id}`),
                  },
                ]}
                onEdit={() => openEdit(kb)}
                onDelete={() => onDelete(kb)}
              />
            }
          />
        ))}
      </ResourceListLayout>

      <ResourceDialog
        open={dialogOpen}
        title={editing ? "编辑知识库" : "新建知识库"}
        onClose={() => {
          setDialogOpen(false);
          setSaveError("");
        }}
        description={editing ? undefined : "向量化模型创建后不可修改。"}
        footer={
          <>
            <button
              type="button"
              className="btn-ghost"
              onClick={() => {
                setDialogOpen(false);
                setSaveError("");
              }}
            >
              取消
            </button>
            <button type="button" className="btn-primary" onClick={onSave}>
              {editing ? "保存" : "创建"}
            </button>
          </>
        }
      >
        {saveError && (
          <KbPageAlert tone="error" message={saveError} onDismiss={() => setSaveError("")} />
        )}
        <input
          className="input-field w-full"
          placeholder="知识库名称"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          className="input-field w-full"
          placeholder="描述（可选）"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-xs text-ink-muted">
            分片大小
            <input
              type="number"
              min={100}
              max={4000}
              className="input-field mt-1 w-full"
              value={chunkSize}
              onChange={(e) => setChunkSize(Number(e.target.value))}
            />
          </label>
          <label className="block text-xs text-ink-muted">
            重叠长度
            <input
              type="number"
              min={0}
              max={500}
              className="input-field mt-1 w-full"
              value={chunkOverlap}
              onChange={(e) => setChunkOverlap(Number(e.target.value))}
            />
          </label>
        </div>
        {!editing && (
          <label className="block text-xs text-ink-muted">
            向量化模型（创建后不可修改，来自
            <a href="/workbench/models" className="text-brand hover:underline">
              模型供应商
            </a>
            ）
            <select
              className="input-field mt-1 w-full"
              value={embeddingModelId}
              onChange={(e) => setEmbeddingModelId(e.target.value)}
            >
              {textEmbeddingModels.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                  {embeddingDimension(m) ? `（${embeddingDimension(m)} 维）` : ""}
                  {m.source === "builtin" ? " · 内置" : ""}
                </option>
              ))}
            </select>
          </label>
        )}
        {editing && (
          <p className="text-xs text-ink-faint">
            向量化模型：{editing.embedding_model_name ?? "—"}（{editing.embedding_dimension}{" "}
            维），创建后不可修改。
          </p>
        )}
        <label className="block text-xs text-ink-muted">
          CLIP 视觉模型（可选，以图搜图）
          <select
            className="input-field mt-1 w-full"
            value={visualModelId}
            onChange={(e) => setVisualModelId(e.target.value)}
          >
            <option value="">不启用</option>
            {clipModels.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
                {embeddingDimension(m) ? `（${embeddingDimension(m)} 维）` : ""}
                {m.source === "builtin" ? " · 内置" : ""}
              </option>
            ))}
          </select>
        </label>
        {clipModels.length === 0 && (
          <p className="text-xs text-ink-faint">
            未找到 CLIP 模型。请执行 model-catalog seed 或在模型页添加 invoke_mode=clip 的 embedding 模型。
          </p>
        )}
        <label className="block text-xs text-ink-muted">
          检索策略
          <select
            className="input-field mt-1 w-full"
            value={retrievalMode}
            onChange={(e) => setRetrievalMode(e.target.value as "vector" | "hybrid")}
          >
            {(kbMeta?.retrieval_modes ?? [
              { value: "vector", label: "纯语义向量" },
              { value: "hybrid", label: "混合（向量 + 关键词）" },
            ]).map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
                {o.hint ? ` — ${o.hint}` : ""}
              </option>
            ))}
          </select>
        </label>
        {retrievalMode === "hybrid" && (
          <label className="block text-xs text-ink-muted">
            混合权重 α
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              className="input-field mt-1 w-full"
              value={hybridAlpha}
              onChange={(e) => setHybridAlpha(Number(e.target.value))}
            />
          </label>
        )}
        <label className="block text-xs text-ink-muted">
          重排模型（可选，RAG 精排）
          <select
            className="input-field mt-1 w-full"
            value={rerankModelId}
            onChange={(e) => setRerankModelId(e.target.value)}
          >
            <option value="">不启用</option>
            {rerankModels.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
                {m.source === "builtin" ? " · 内置" : ""}
              </option>
            ))}
          </select>
        </label>
        {rerankModelId && (
          <label className="block text-xs text-ink-muted">
            重排候选数（首轮召回上限）
            <input
              type="number"
              min={5}
              max={100}
              className="input-field mt-1 w-full"
              value={rerankCandidateK}
              onChange={(e) => setRerankCandidateK(Number(e.target.value))}
            />
          </label>
        )}
      </ResourceDialog>
      {confirmDialog}
    </>
  );
}
