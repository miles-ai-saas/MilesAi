"use client";

/** 生成物媒体资产：列表、预览、升格入库。 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { filterBySearch } from "@/lib/filter-search";
import { mediaAssetKindLabel, mediaAssetSourceLabel } from "@/lib/media-asset-labels";
import { ChatArtifactMedia } from "@/components/agent/ChatArtifactMedia";
import type { KnowledgeBase, MediaAsset } from "@/lib/types";

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

export default function MediaAssetsPage() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState("");
  const [promoted, setPromoted] = useState<"" | "yes" | "no">("");
  const [msg, setMsg] = useState("");
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [promoteTarget, setPromoteTarget] = useState<MediaAsset | null>(null);
  const [promoteKbId, setPromoteKbId] = useState("");
  const [promoteBusy, setPromoteBusy] = useState(false);

  const list = usePagedList(
    useCallback(
      (p, s) =>
        api.listMediaAssets(p, s, {
          kind: kind || undefined,
          has_kb_document:
            promoted === "yes" ? true : promoted === "no" ? false : undefined,
        }),
      [kind, promoted],
    ),
    { enabled: ready, resetKey: `${kind}-${promoted}` },
  );
  const { requestConfirm, confirmDialog } = useConfirmAction();

  useEffect(() => {
    if (!ready) return;
    void api.listKbs(1, 100).then((r) => setKbs(r.items));
  }, [ready]);

  const filtered = useMemo(
    () =>
      filterBySearch(list.items, search, (a) =>
        `${a.title ?? ""} ${a.prompt ?? ""} ${a.kind} ${a.source} ${a.attachment?.filename ?? ""}`.trim(),
      ),
    [list.items, search],
  );

  const onDelete = (a: MediaAsset) => {
    requestConfirm({
      title: "删除素材",
      message: <>确定删除「{a.title ?? a.attachment?.filename ?? a.id}」？</>,
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deleteMediaAsset(a.id);
        await list.reload();
        setMsg("已删除");
      },
    });
  };

  const openPromote = (a: MediaAsset) => {
    setPromoteTarget(a);
    setPromoteKbId(kbs[0]?.id ?? "");
    setMsg("");
  };

  const onPromote = async () => {
    if (!promoteTarget || !promoteKbId) return;
    setPromoteBusy(true);
    setMsg("");
    try {
      await api.promoteMediaAssetToKb(promoteTarget.id, {
        kb_id: promoteKbId,
        filename: promoteTarget.title ?? promoteTarget.attachment?.filename,
        run_parse: true,
      });
      setPromoteTarget(null);
      await list.reload();
      setMsg("已加入知识库并开始解析");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "升格失败");
    } finally {
      setPromoteBusy(false);
    }
  };

  return (
    <>
      <ResourceListLayout
        title="生成素材"
        description="智能体与流程产生的图片/视频；可预览、管理，图片可升格写入知识库（不自动入库）。"
        searchPlaceholder="搜索标题、prompt、文件名"
        search={search}
        onSearchChange={setSearch}
        loading={list.loading}
        headerAction={
          <div className="flex flex-wrap items-center gap-2">
            <select
              className="input-field w-auto text-sm"
              value={kind}
              onChange={(e) => setKind(e.target.value)}
            >
              <option value="">全部类型</option>
              <option value="image">图片</option>
              <option value="video">视频</option>
            </select>
            <select
              className="input-field w-auto text-sm"
              value={promoted}
              onChange={(e) => setPromoted(e.target.value as "" | "yes" | "no")}
            >
              <option value="">全部状态</option>
              <option value="no">未入库</option>
              <option value="yes">已入库</option>
            </select>
          </div>
        }
        footer={
          !list.loading ? (
            <ResourceListFooter
              page={list.page}
              size={list.size}
              total={list.total}
              onPageChange={list.setPage}
            />
          ) : null
        }
      >
        {msg && <p className="mb-4 text-sm text-ink-muted">{msg}</p>}
        {filtered.length === 0 && !list.loading ? (
          <p className="text-sm text-ink-muted">
            暂无生成素材。在智能体中开启生成工具并生图/生视频，或在流程中使用生图/生视频节点。
          </p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((a) => (
              <article
                key={a.id}
                className="flex flex-col rounded-lg border border-line bg-surface p-3 shadow-sm"
              >
                <div className="mb-2 flex min-h-[120px] items-center justify-center rounded-md bg-surface-muted">
                  <ChatArtifactMedia
                    kind={a.kind}
                    attachmentId={a.attachment_id}
                    mimeType={a.attachment?.mime_type}
                    caption={a.title ?? undefined}
                    posterAttachmentId={
                      a.kind === "video"
                        ? a.cover_attachment_id ?? a.cover_attachment?.id
                        : undefined
                    }
                  />
                </div>
                <p className="truncate text-sm font-medium text-ink">
                  {a.title ?? a.attachment?.filename ?? "未命名"}
                </p>
                <p className="mt-1 text-xs text-ink-muted">
                  {mediaAssetKindLabel(a.kind)} · {mediaAssetSourceLabel(a.source)}
                  {a.attachment?.file_size != null
                    ? ` · ${formatBytes(a.attachment.file_size)}`
                    : ""}
                </p>
                {a.prompt && (
                  <p className="mt-2 line-clamp-2 text-xs text-ink-faint" title={a.prompt}>
                    {a.prompt}
                  </p>
                )}
                <p className="mt-1 text-[10px] text-ink-faint">
                  {new Date(a.created_at).toLocaleString()}
                  {a.kb_document_id ? " · 已入库" : ""}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {!a.kb_document_id && (a.kind === "image" || a.kind === "video") && kbs.length > 0 && (
                    <button
                      type="button"
                      className="btn-sm-primary text-xs"
                      onClick={() => openPromote(a)}
                    >
                      加入知识库
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn-sm-ghost text-xs text-red-600"
                    onClick={() => onDelete(a)}
                  >
                    删除
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </ResourceListLayout>

      {promoteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl border border-line bg-surface p-5 shadow-lg">
            <h2 className="text-base font-semibold text-ink">加入知识库</h2>
            <p className="mt-1 text-sm text-ink-muted">
              将复制文件到所选知识库并触发解析（占用存储配额）。
            </p>
            <label className="mt-4 block text-xs font-medium text-ink-muted">
              目标知识库
              <select
                className="input-field mt-1 w-full text-sm"
                value={promoteKbId}
                onChange={(e) => setPromoteKbId(e.target.value)}
              >
                {kbs.map((kb) => (
                  <option key={kb.id} value={kb.id}>
                    {kb.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                className="btn-secondary text-sm"
                disabled={promoteBusy}
                onClick={() => setPromoteTarget(null)}
              >
                取消
              </button>
              <button
                type="button"
                className="btn-primary text-sm"
                disabled={promoteBusy || !promoteKbId}
                onClick={() => void onPromote()}
              >
                {promoteBusy ? "处理中…" : "确认"}
              </button>
            </div>
          </div>
        </div>
      )}
      {confirmDialog}
    </>
  );
}
