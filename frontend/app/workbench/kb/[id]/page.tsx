"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { DocumentStatusBadge } from "@/components/kb/DocumentStatusBadge";
import { KbMetaChips } from "@/components/kb/KbMetaChips";
import { KbPageAlert } from "@/components/kb/KbPageAlert";
import { KbQuotaBar } from "@/components/kb/KbQuotaBar";
import { KbUploadZone } from "@/components/kb/KbUploadZone";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import {
  canRetryDocument,
  isDocumentProcessing,
} from "@/lib/document-status";
import { formatFileSize } from "@/lib/format-bytes";
import { kbFileIcon } from "@/lib/kb-file-icon";
import { retrievalModeLabel, SEARCH_SOURCE_LABEL } from "@/lib/kb-labels";
import type { Document, KnowledgeBase, KbQuota } from "@/lib/types";

type TabKey = "documents" | "search" | "logs";
type DocFilter = "all" | "ready" | "processing" | "failed";
type AlertState = { tone: "success" | "error" | "info"; message: string } | null;

const TABS: { key: TabKey; label: string }[] = [
  { key: "documents", label: "文档" },
  { key: "search", label: "检索测试" },
  { key: "logs", label: "检索记录" },
];

const DOC_FILTERS: { key: DocFilter; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "ready", label: "可检索" },
  { key: "processing", label: "处理中" },
  { key: "failed", label: "失败" },
];

function matchDocFilter(status: string, filter: DocFilter): boolean {
  if (filter === "all") return true;
  if (filter === "ready") return status === "ready";
  if (filter === "processing") return isDocumentProcessing(status);
  if (filter === "failed") return status.includes("failed");
  return true;
}

export default function KbDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { ready } = useRequireAuth();
  const [tab, setTab] = useState<TabKey>("documents");
  const [kb, setKb] = useState<KnowledgeBase | null>(null);
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
  const [docFilter, setDocFilter] = useState<DocFilter>("all");
  const [expandedFailId, setExpandedFailId] = useState<string | null>(null);
  const [searchQ, setSearchQ] = useState("");
  const [searchTopK, setSearchTopK] = useState(5);
  const [searchMode, setSearchMode] = useState<"default" | "vector" | "hybrid">("default");
  const [searching, setSearching] = useState(false);
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
  const [alert, setAlert] = useState<AlertState>(null);
  const [docsRefreshing, setDocsRefreshing] = useState(false);
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const docs = usePagedList(useCallback((p, s) => api.listDocuments(id, p, s), [id]), {
    enabled: ready && !!id,
    resetKey: id,
  });

  const logs = usePagedList(
    useCallback((p, s) => api.listKbSearchLogs(id, p, s), [id]),
    { enabled: ready && !!id && tab === "logs", resetKey: `${id}-${tab}` },
  );

  const filteredDocs = useMemo(
    () => docs.items.filter((d) => matchDocFilter(d.status, docFilter)),
    [docs.items, docFilter],
  );

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
    Promise.all([reloadKb(), reloadQuota()]).catch((e) =>
      setAlert({ tone: "error", message: e instanceof Error ? e.message : "加载失败" }),
    );
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

  const onUploadFile = async (file: File) => {
    setUploading(true);
    setAlert(null);
    try {
      await api.uploadDocument(id, file);
      await Promise.all([docs.reload(), reloadQuota()]);
      setAlert({ tone: "success", message: `「${file.name}」已上传，正在后台解析入库。` });
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

  const onSearch = async () => {
    if (!searchQ.trim()) return;
    setSearching(true);
    setAlert(null);
    try {
      const res = await api.searchKb(id, searchQ.trim(), {
        mode: searchMode,
        top_k: searchTopK,
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

  if (!kb) {
    return (
      <div className="mx-auto max-w-5xl space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-surface-muted" />
        <div className="h-32 animate-pulse rounded-xl bg-surface-muted" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <nav className="flex items-center gap-2 text-sm text-ink-muted">
        <Link href="/workbench/kb" className="text-brand hover:underline">
          知识库
        </Link>
        <span aria-hidden>/</span>
        <span className="truncate font-medium text-ink">{kb.name}</span>
      </nav>

      {alert && (
        <KbPageAlert
          tone={alert.tone}
          message={alert.message}
          onDismiss={() => setAlert(null)}
        />
      )}

      <header className="rounded-xl border border-line bg-surface p-5 shadow-card">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <h1 className="text-xl font-bold tracking-tight text-ink">{kb.name}</h1>
            <p className="mt-1 text-sm text-ink-muted">{kb.description || "暂无描述"}</p>
            <KbMetaChips kb={kb} />
            <KbQuotaBar
              quota={quota}
              loading={quotaLoading}
              variant="detail"
              className="mt-2"
            />
          </div>
          <div className="flex shrink-0 gap-2">
            <button type="button" className="btn-ghost text-sm" onClick={openSettings}>
              设置
            </button>
            <button
              type="button"
              className="btn-ghost text-sm text-red-600 hover:bg-red-50"
              onClick={onDeleteKb}
            >
              删除
            </button>
          </div>
        </div>
        {hasProcessing && (
          <p className="mt-4 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-900">
            有文档正在后台入库，请点击文档列表旁的刷新按钮查看最新状态。
          </p>
        )}
      </header>

      <div className="flex gap-1 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`rounded-t-lg px-4 py-2.5 text-sm transition ${
              tab === t.key
                ? "bg-surface font-medium text-brand shadow-card ring-1 ring-line ring-b-0"
                : "text-ink-muted hover:bg-surface-muted/50 hover:text-ink"
            }`}
          >
            {t.label}
            {t.key === "documents" && docs.total > 0 && (
              <span className="ml-1.5 text-xs text-ink-faint">({docs.total})</span>
            )}
          </button>
        ))}
      </div>

      {tab === "documents" && (
        <section className="space-y-4">
          <KbUploadZone uploading={uploading} onFile={onUploadFile} />

          <div className="rounded-xl border border-line bg-surface p-4 shadow-card">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-sm font-semibold text-ink">文档列表</h2>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  className="btn-ghost flex h-8 w-8 items-center justify-center p-0"
                  aria-label="刷新"
                  title="刷新"
                  disabled={docsRefreshing || docs.loading}
                  onClick={onRefreshDocuments}
                >
                  <svg
                    className={`h-4 w-4 ${docsRefreshing ? "animate-spin" : ""}`}
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    aria-hidden
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182"
                    />
                  </svg>
                </button>
                <div className="flex flex-wrap gap-1">
                {DOC_FILTERS.map((f) => (
                  <button
                    key={f.key}
                    type="button"
                    onClick={() => setDocFilter(f.key)}
                    className={`rounded-full px-2.5 py-1 text-xs transition ${
                      docFilter === f.key
                        ? "bg-brand text-white"
                        : "bg-surface-muted text-ink-muted hover:text-ink"
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
                </div>
              </div>
            </div>
            {docFilter !== "all" && (
              <p className="mt-2 text-xs text-ink-faint">筛选仅作用于当前页；切换页码可查看更多。</p>
            )}

            {docs.loading ? (
              <ul className="mt-4 space-y-2">
                {[1, 2, 3].map((i) => (
                  <li key={i} className="h-14 animate-pulse rounded-lg bg-surface-muted" />
                ))}
              </ul>
            ) : docs.items.length === 0 ? (
              <p className="mt-6 text-center text-sm text-ink-muted">
                暂无文档。上传文件后将自动解析、分片并写入向量库。
              </p>
            ) : filteredDocs.length === 0 ? (
              <p className="mt-6 text-center text-sm text-ink-muted">当前筛选下无文档。</p>
            ) : (
              <>
                <ul className="mt-4 space-y-2">
                  {filteredDocs.map((d) => (
                    <DocumentRow
                      key={d.id}
                      doc={d}
                      retrying={retryingId === d.id}
                      expanded={expandedFailId === d.id}
                      onToggleFail={() =>
                        setExpandedFailId((prev) => (prev === d.id ? null : d.id))
                      }
                      onRetry={() => onRetry(d.id)}
                      onDelete={() => onRequestDeleteDoc(d)}
                    />
                  ))}
                </ul>
                <ResourceListFooter
                  className="mt-4 border-t border-line pt-3"
                  page={docs.page}
                  size={docs.size}
                  total={docs.total}
                  onPageChange={docs.setPage}
                />
              </>
            )}
          </div>
        </section>
      )}

      {tab === "search" && (
        <section className="rounded-xl border border-line bg-surface p-5 shadow-card">
          <h2 className="text-sm font-semibold text-ink">检索测试</h2>
          <p className="mt-1 text-xs text-ink-faint">
            默认使用本库配置（{retrievalModeLabel(kb.retrieval_mode)}）。专有名词、编号可尝试「混合」。
          </p>
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
            <label className="min-w-0 flex-1">
              <span className="sr-only">检索问题</span>
              <input
                className="input-field w-full"
                value={searchQ}
                onChange={(e) => setSearchQ(e.target.value)}
                placeholder="输入问题或关键词"
                onKeyDown={(e) => e.key === "Enter" && onSearch()}
              />
            </label>
            <div className="flex flex-wrap items-center gap-2">
              <select
                className="input-field w-auto min-w-[7rem]"
                value={searchMode}
                onChange={(e) => setSearchMode(e.target.value as typeof searchMode)}
              >
                <option value="default">按库配置</option>
                <option value="vector">纯语义</option>
                <option value="hybrid">混合</option>
              </select>
              <label className="flex items-center gap-1 text-xs text-ink-muted">
                Top
                <input
                  type="number"
                  min={1}
                  max={50}
                  className="input-field w-14"
                  value={searchTopK}
                  onChange={(e) => setSearchTopK(Number(e.target.value))}
                />
              </label>
              <button type="button" onClick={onSearch} className="btn-primary" disabled={searching}>
                {searching ? "检索中…" : "检索"}
              </button>
            </div>
          </div>
          {searchResultMode && (
            <p className="mt-3 text-xs text-ink-faint">
              模式 <span className="font-medium text-ink">{searchResultMode}</span>
              {searchHits.length === 0 ? " · 无命中" : ` · ${searchHits.length} 条结果`}
            </p>
          )}
          <ul className="mt-4 space-y-3">
            {searchHits.length === 0 && searchResultMode && (
              <li className="rounded-lg border border-dashed border-line px-4 py-6 text-center text-sm text-ink-muted">
                无命中结果，可调整问法或切换混合检索后重试
              </li>
            )}
            {searchHits.map((h, i) => (
              <li key={i} className="rounded-lg border border-line bg-surface-muted/40 p-4">
                <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-ink-faint">
                  <span className="rounded bg-surface px-1.5 py-0.5 font-mono text-ink">
                    #{i + 1}
                  </span>
                  <span className="font-mono font-medium text-brand">{h.score.toFixed(3)}</span>
                  {h.score_vector != null && <span>向量 {h.score_vector.toFixed(2)}</span>}
                  {h.score_keyword != null && <span>关键词 {h.score_keyword.toFixed(2)}</span>}
                  {h.filename && <span className="truncate">· {h.filename}</span>}
                </div>
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink">{h.content}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {tab === "logs" && (
        <section className="rounded-xl border border-line bg-surface p-5 shadow-card">
          <h2 className="text-sm font-semibold text-ink">检索记录</h2>
          <p className="mt-1 text-xs text-ink-faint">
            记录本库的 API 调试、智能体 RAG 与流程检索（仅本租户可见）
          </p>
          {logs.loading ? (
            <p className="mt-4 text-sm text-ink-muted">加载中…</p>
          ) : logs.items.length === 0 ? (
            <p className="mt-6 text-center text-sm text-ink-muted">
              暂无记录。在「检索测试」或绑定本库的智能体对话后会出现。
            </p>
          ) : (
            <>
              <ul className="mt-4 divide-y divide-line">
                {logs.items.map((log) => (
                  <li key={log.id} className="py-3 first:pt-0">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-ink-faint">
                      <time dateTime={log.created_at}>
                        {new Date(log.created_at).toLocaleString()}
                      </time>
                      <span className="rounded-md bg-surface-muted px-1.5 py-0.5">
                        {log.retrieval_mode}
                      </span>
                      <span>{SEARCH_SOURCE_LABEL[log.source] ?? log.source}</span>
                      <span>
                        {log.hit_count} 命中 · {log.latency_ms} ms
                      </span>
                    </div>
                    <p className="mt-1.5 text-sm text-ink">{log.query}</p>
                  </li>
                ))}
              </ul>
              <ResourceListFooter
                className="mt-4 border-t border-line pt-3"
                page={logs.page}
                size={logs.size}
                total={logs.total}
                onPageChange={logs.setPage}
              />
            </>
          )}
        </section>
      )}

      {confirmDialog}

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
            混合权重 α（1=偏向量，0=偏关键词）
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

function DocumentRow({
  doc,
  retrying,
  expanded,
  onToggleFail,
  onRetry,
  onDelete,
}: {
  doc: Document;
  retrying: boolean;
  expanded: boolean;
  onToggleFail: () => void;
  onRetry: () => void;
  onDelete: () => void;
}) {
  const icon = kbFileIcon(doc.filename);
  const hasFail = Boolean(doc.fail_reason);

  return (
    <li className="flex gap-3 rounded-lg border border-line bg-surface-muted/20 px-3 py-3 transition hover:bg-surface-muted/40">
      <div
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-surface text-[10px] font-bold text-ink-muted ring-1 ring-line"
        aria-hidden
      >
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="truncate font-medium text-ink">{doc.filename}</p>
          <DocumentStatusBadge status={doc.status} pulse={isDocumentProcessing(doc.status)} />
        </div>
        <p className="mt-0.5 text-xs text-ink-faint">
          {formatFileSize(doc.file_size)} · {new Date(doc.created_at).toLocaleString()}
        </p>
        {hasFail && (
          <div className="mt-2">
            <button
              type="button"
              className="text-left text-xs text-red-700 hover:underline"
              onClick={onToggleFail}
            >
              {expanded ? "收起失败原因" : "查看失败原因"}
            </button>
            {expanded && (
              <p className="mt-1 whitespace-pre-wrap rounded-md bg-red-50 px-2 py-1.5 text-xs text-red-900">
                {doc.fail_reason}
              </p>
            )}
          </div>
        )}
      </div>
      <div className="flex shrink-0 flex-col items-end justify-center gap-1 sm:flex-row sm:items-center">
        {canRetryDocument(doc.status) && (
          <button
            type="button"
            className="btn-ghost px-2 py-1 text-xs"
            disabled={retrying}
            onClick={onRetry}
          >
            {retrying ? "提交中…" : "重试"}
          </button>
        )}
        <button
          type="button"
          className="btn-ghost px-2 py-1 text-xs text-red-600 hover:bg-red-50"
          onClick={onDelete}
        >
          删除
        </button>
      </div>
    </li>
  );
}
