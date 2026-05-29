"use client";

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { KbPageAlert } from "@/features/kb/components/KbPageAlert";
import type { KbPageVm } from "@/features/kb/hooks/use-kb-page";
import { embeddingDimension } from "@/features/kb/lib/kb-page-shared";

export function KbFormDialog({ vm }: { vm: KbPageVm }) {
  const {
    dialogOpen,
    editing,
    closeDialog,
    onSave,
    saveError,
    setSaveError,
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
    kbMeta,
  } = vm;

  return (
    <ResourceDialog
      open={dialogOpen}
      title={editing ? "编辑知识库" : "新建知识库"}
      onClose={closeDialog}
      description={editing ? undefined : "向量化模型创建后不可修改。"}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={closeDialog}>
            取消
          </button>
          <button type="button" className="btn-primary" onClick={onSave}>
            {editing ? "保存" : "创建"}
          </button>
        </>
      }
    >
      {saveError && <KbPageAlert tone="error" message={saveError} onDismiss={() => setSaveError("")} />}
      <input className="input-field w-full" placeholder="知识库名称" value={name} onChange={(e) => setName(e.target.value)} />
      <input className="input-field w-full" placeholder="描述（可选）" value={description} onChange={(e) => setDescription(e.target.value)} />
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
          <select className="input-field mt-1 w-full" value={embeddingModelId} onChange={(e) => setEmbeddingModelId(e.target.value)}>
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
          向量化模型：{editing.embedding_model_name ?? "—"}（{editing.embedding_dimension} 维），创建后不可修改。
        </p>
      )}
      <label className="block text-xs text-ink-muted">
        CLIP 视觉模型（可选，以图搜图）
        <select className="input-field mt-1 w-full" value={visualModelId} onChange={(e) => setVisualModelId(e.target.value)}>
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
        <p className="text-xs text-ink-faint">未找到 CLIP 模型。请执行 model-catalog seed 或在模型页添加 invoke_mode=clip 的 embedding 模型。</p>
      )}
      <label className="block text-xs text-ink-muted">
        检索策略
        <select className="input-field mt-1 w-full" value={retrievalMode} onChange={(e) => setRetrievalMode(e.target.value as "vector" | "hybrid")}>
          {(
            kbMeta?.retrieval_modes ?? [
              { value: "vector", label: "纯语义向量" },
              { value: "hybrid", label: "混合（向量 + 关键词）" },
            ]
          ).map((o) => (
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
        <select className="input-field mt-1 w-full" value={rerankModelId} onChange={(e) => setRerankModelId(e.target.value)}>
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
  );
}
