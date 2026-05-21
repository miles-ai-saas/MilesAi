"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import type { KnowledgeBase } from "@/lib/types";

export default function KbDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { ready } = useRequireAuth();
  const [kb, setKb] = useState<KnowledgeBase | null>(null);
  const [uploading, setUploading] = useState(false);
  const [searchQ, setSearchQ] = useState("");
  const [searchHits, setSearchHits] = useState<{ content: string; score: number }[]>([]);
  const [msg, setMsg] = useState("");

  const docs = usePagedList(useCallback((p, s) => api.listDocuments(id, p, s), [id]), {
    enabled: ready && !!id,
    resetKey: id,
  });

  useEffect(() => {
    if (!ready || !id) return;
    api.getKb(id).then(setKb).catch((e) => setMsg(e instanceof Error ? e.message : "加载失败"));
  }, [ready, id]);

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

  const onSearch = async () => {
    if (!searchQ.trim()) return;
    const res = await api.searchKb(id, searchQ.trim());
    setSearchHits(res.hits.map((h) => ({ content: h.content, score: h.score })));
  };

  const onDelete = async (docId: string) => {
    if (!confirm("确定删除该文档？")) return;
    await api.deleteDocument(id, docId);
    await docs.reload();
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

      <section className="rounded-xl border border-line bg-surface shadow-card p-4">
        <h1 className="text-lg font-bold">{kb.name}</h1>
        <p className="text-sm text-ink-muted">{kb.description || "无描述"}</p>
        <label className="mt-4 inline-block cursor-pointer rounded bg-brand px-4 py-2 text-sm text-white">
          {uploading ? "上传中…" : "上传文档"}
          <input type="file" className="hidden" onChange={onUpload} disabled={uploading} />
        </label>
        {msg && <p className="mt-2 text-sm text-ink-muted">{msg}</p>}
      </section>

      <section className="rounded-xl border border-line bg-surface shadow-card p-4">
        <h2 className="text-sm font-semibold">文档列表</h2>
        {docs.loading ? (
          <p className="mt-3 text-sm text-ink-muted">加载中…</p>
        ) : (
          <>
            <ul className="mt-3 divide-y text-sm">
              {docs.items.map((d) => (
                <li key={d.id} className="flex items-center justify-between py-2">
                  <div>
                    <p className="font-medium">{d.filename}</p>
                    <p className="text-xs text-ink-muted">
                      {d.status} · {(d.file_size / 1024).toFixed(1)} KB
                    </p>
                    {d.fail_reason && <p className="text-xs text-red-600">{d.fail_reason}</p>}
                  </div>
                  <button
                    type="button"
                    className="text-xs text-red-600"
                    onClick={() => onDelete(d.id)}
                  >
                    删除
                  </button>
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

      <section className="rounded-xl border border-line bg-surface shadow-card p-4">
        <h2 className="text-sm font-semibold">检索测试</h2>
        <div className="mt-2 flex gap-2">
          <input
            className="flex-1 rounded border px-3 py-2 text-sm"
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            placeholder="输入问题"
          />
          <button type="button" onClick={onSearch} className="rounded bg-brand px-4 py-2 text-sm text-white">
            检索
          </button>
        </div>
        <ul className="mt-3 space-y-2 text-xs text-ink-muted">
          {searchHits.map((h, i) => (
            <li key={i} className="rounded bg-surface-muted p-2">
              <span className="text-ink-faint">[{h.score.toFixed(2)}]</span> {h.content}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
