"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { canRetryDocument, documentStatusLabel } from "@/lib/document-status";
import type { KnowledgeBase } from "@/lib/types";

export default function KbDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { ready } = useRequireAuth();
  const [kb, setKb] = useState<KnowledgeBase | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editChunkSize, setEditChunkSize] = useState(500);
  const [editChunkOverlap, setEditChunkOverlap] = useState(50);
  const [editRetrievalMode, setEditRetrievalMode] = useState<"vector" | "hybrid">("vector");
  const [editHybridAlpha, setEditHybridAlpha] = useState(0.5);
  const [uploading, setUploading] = useState(false);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [searchQ, setSearchQ] = useState("");
  const [searchMode, setSearchMode] = useState<"default" | "vector" | "hybrid">("default");
  const [searchResultMode, setSearchResultMode] = useState("");
  const [searchHits, setSearchHits] = useState<
    {
      content: string;
      score: number;
      score_vector?: number | null;
      score_keyword?: number | null;
      filename?: string;
    }[]
  >([]);
  const [msg, setMsg] = useState("");

  const docs = usePagedList(useCallback((p, s) => api.listDocuments(id, p, s), [id]), {
    enabled: ready && !!id,
    resetKey: id,
  });

  const reloadKb = useCallback(() => {
    if (!id) return;
    return api.getKb(id).then(setKb);
  }, [id]);

  useEffect(() => {
    if (!ready || !id) return;
    reloadKb().catch((e) => setMsg(e instanceof Error ? e.message : "加载失败"));
  }, [ready, id, reloadKb]);

  const hasProcessing = docs.items.some((d) =>
    ["pending", "parsing", "embedding"].includes(d.status),
  );

  useEffect(() => {
    if (!hasProcessing || !ready) return;
    const t = setInterval(() => docs.reload(), 4000);
    return () => clearInterval(t);
  }, [hasProcessing, ready, docs.reload]);

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
    setMsg("设置已保存（分片参数仅影响之后上传/重试的文档）");
  };

  const onDeleteKb = async () => {
    if (!kb) return;
    if (!confirm(`确定删除知识库「${kb.name}」？将删除其下全部文档与向量数据。`)) return;
    await api.deleteKb(kb.id);
    router.push("/workbench/kb");
  };

  const onUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setMsg("");
    try {
      await api.uploadDocument(id, file);
      await docs.reload();
      setMsg("上传成功，文档已进入解析队列");
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "上传失败");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const onRetry = async (docId: string) => {
    setRetryingId(docId);
    setMsg("");
    try {
      await api.retryDocument(id, docId);
      await docs.reload();
      setMsg("已重新提交入库任务");
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "重试失败");
    } finally {
      setRetryingId(null);
    }
  };

  const onSearch = async () => {
    if (!searchQ.trim()) return;
    const res = await api.searchKb(id, searchQ.trim(), { mode: searchMode });
    setSearchResultMode(res.mode);
    setSearchHits(res.hits);
  };

  const onDelete = async (docId: string) => {
    if (!confirm("确定删除该文档？")) return;
    await api.deleteDocument(id, docId);
    await docs.reload();
    setMsg("文档已删除");
  };

  if (!kb) return <p className="text-ink-muted">加载中…</p>;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center gap-2 text-sm text-ink-muted">
        <Link href="/workbench/kb" className="text-brand hover:underline">
          知识库
        </Link>
        <span>/</span>
        <span className="text-ink">{kb.name}</span>
      </div>

      <section className="rounded-xl border border-line bg-surface p-4 shadow-card">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-lg font-bold">{kb.name}</h1>
            <p className="text-sm text-ink-muted">{kb.description || "无描述"}</p>
            <p className="mt-2 text-xs text-ink-faint">
              向量：{kb.embedding_model_name ?? "—"} · {kb.embedding_dimension} 维 · 分片 {kb.chunk_size}/
              {kb.chunk_overlap} · 检索 {kb.retrieval_mode === "hybrid" ? "混合" : "语义"}
              {kb.retrieval_mode === "hybrid" ? ` (α=${kb.hybrid_alpha ?? 0.5})` : ""}
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
            <button type="button" className="btn-ghost text-sm" onClick={openSettings}>
              设置
            </button>
            <button type="button" className="text-sm text-red-600 hover:underline" onClick={onDeleteKb}>
              删除知识库
            </button>
          </div>
        </div>
        <label className="mt-4 inline-block cursor-pointer rounded bg-brand px-4 py-2 text-sm text-white">
          {uploading ? "上传中…" : "上传文档 / 多模态"}
          <input
            type="file"
            className="hidden"
            accept=".txt,.md,.pdf,.jpg,.jpeg,.png,.webp,.mp3,.wav,.m4a,.ogg"
            onChange={onUpload}
            disabled={uploading}
          />
        </label>
        <p className="mt-2 text-xs text-ink-faint">
          支持 TXT/MD/PDF、图片（JPG/PNG/WebP，OCR 可选）、音频（MP3/WAV，Whisper 可选）
        </p>
        {msg && <p className="mt-2 text-sm text-ink-muted">{msg}</p>}
      </section>

      <section className="rounded-xl border border-line bg-surface p-4 shadow-card">
        <h2 className="text-sm font-semibold">文档列表</h2>
        {docs.loading ? (
          <p className="mt-3 text-sm text-ink-muted">加载中…</p>
        ) : docs.items.length === 0 ? (
          <p className="mt-3 text-sm text-ink-muted">暂无文档，请上传文件开始入库。</p>
        ) : (
          <>
            <ul className="mt-3 divide-y text-sm">
              {docs.items.map((d) => (
                <li key={d.id} className="flex items-center justify-between gap-3 py-2">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium truncate">{d.filename}</p>
                    <p className="text-xs text-ink-muted">
                      <span
                        className={
                          d.status.includes("failed")
                            ? "text-red-600"
                            : d.status === "ready"
                              ? "text-emerald-700"
                              : ""
                        }
                      >
                        {documentStatusLabel(d.status)}
                      </span>
                      {" · "}
                      {(d.file_size / 1024).toFixed(1)} KB
                    </p>
                    {d.fail_reason && (
                      <p className="text-xs text-red-600 line-clamp-2">{d.fail_reason}</p>
                    )}
                  </div>
                  <div className="flex shrink-0 gap-2">
                    {canRetryDocument(d.status) && (
                      <button
                        type="button"
                        className="text-xs text-brand hover:underline"
                        disabled={retryingId === d.id}
                        onClick={() => onRetry(d.id)}
                      >
                        {retryingId === d.id ? "提交中…" : "重试"}
                      </button>
                    )}
                    <button
                      type="button"
                      className="text-xs text-red-600 hover:underline"
                      onClick={() => onDelete(d.id)}
                    >
                      删除
                    </button>
                  </div>
                </li>
              ))}
            </ul>
            <ResourceListFooter
              className="mt-3"
              page={docs.page}
              size={docs.size}
              total={docs.total}
              onPageChange={docs.setPage}
            />
          </>
        )}
      </section>

      <section className="rounded-xl border border-line bg-surface p-4 shadow-card">
        <h2 className="text-sm font-semibold">检索测试</h2>
        <div className="mt-2 flex flex-wrap gap-2">
          <input
            className="input-field min-w-[12rem] flex-1"
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            placeholder="输入问题"
            onKeyDown={(e) => e.key === "Enter" && onSearch()}
          />
          <select
            className="input-field w-auto"
            value={searchMode}
            onChange={(e) => setSearchMode(e.target.value as typeof searchMode)}
          >
            <option value="default">按库配置</option>
            <option value="vector">纯语义</option>
            <option value="hybrid">混合</option>
          </select>
          <button type="button" onClick={onSearch} className="btn-primary">
            检索
          </button>
        </div>
        {searchResultMode && (
          <p className="mt-2 text-xs text-ink-faint">实际模式：{searchResultMode}</p>
        )}
        <ul className="mt-3 space-y-2 text-xs text-ink-muted">
          {searchHits.map((h, i) => (
            <li key={i} className="rounded bg-surface-muted p-2">
              <span className="text-ink-faint">
                [{h.score.toFixed(3)}]
                {h.score_vector != null ? ` V:${h.score_vector.toFixed(2)}` : ""}
                {h.score_keyword != null ? ` K:${h.score_keyword.toFixed(2)}` : ""}
                {h.filename ? ` ${h.filename}` : ""}
              </span>{" "}
              {h.content}
            </li>
          ))}
        </ul>
      </section>

      <ResourceDialog
        open={settingsOpen}
        title="知识库设置"
        onClose={() => setSettingsOpen(false)}
        footer={
          <>
            <button type="button" className="btn-ghost" onClick={() => setSettingsOpen(false)}>
              取消
            </button>
            <button type="button" className="btn-primary" onClick={onSaveSettings}>
              保存
            </button>
          </>
        }
      >
        <input
          className="input-field w-full"
          placeholder="名称"
          value={editName}
          onChange={(e) => setEditName(e.target.value)}
        />
        <input
          className="input-field w-full"
          placeholder="描述（可选）"
          value={editDesc}
          onChange={(e) => setEditDesc(e.target.value)}
        />
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-xs text-ink-muted">
            分片大小
            <input
              type="number"
              min={100}
              max={4000}
              className="input-field mt-1 w-full"
              value={editChunkSize}
              onChange={(e) => setEditChunkSize(Number(e.target.value))}
            />
          </label>
          <label className="block text-xs text-ink-muted">
            重叠长度
            <input
              type="number"
              min={0}
              max={500}
              className="input-field mt-1 w-full"
              value={editChunkOverlap}
              onChange={(e) => setEditChunkOverlap(Number(e.target.value))}
            />
          </label>
        </div>
        <label className="block text-xs text-ink-muted">
          检索策略
          <select
            className="input-field mt-1 w-full"
            value={editRetrievalMode}
            onChange={(e) => setEditRetrievalMode(e.target.value as "vector" | "hybrid")}
          >
            <option value="vector">纯语义向量</option>
            <option value="hybrid">混合（向量 + 关键词）</option>
          </select>
        </label>
        {editRetrievalMode === "hybrid" && (
          <label className="block text-xs text-ink-muted">
            混合权重 α（Weaviate：1=偏向量，0=偏关键词）
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              className="input-field mt-1 w-full"
              value={editHybridAlpha}
              onChange={(e) => setEditHybridAlpha(Number(e.target.value))}
            />
          </label>
        )}
        <p className="text-xs text-ink-faint">
          向量化模型 {kb.embedding_model_name ?? "—"}（{kb.embedding_dimension} 维）创建后不可修改。
        </p>
      </ResourceDialog>
    </div>
  );
}
