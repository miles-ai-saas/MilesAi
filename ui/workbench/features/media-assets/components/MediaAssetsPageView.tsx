"use client";

import { MediaAssetCard } from "@/features/media-assets/components/MediaAssetCard";
import { MediaAssetPromoteDialog } from "@/features/media-assets/components/MediaAssetPromoteDialog";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import type { MediaAssetsPageVm } from "@/features/media-assets/hooks/use-media-assets-page";

const MEDIA_ASSETS_PAGE_DESC = "智能体与流程产生的图片/视频；可预览、管理，图片可升格写入知识库（不自动入库）。";

export function MediaAssetsPageView({ vm }: { vm: MediaAssetsPageVm }) {
  const {
    search,
    setSearch,
    kind,
    setKind,
    promoted,
    setPromoted,
    msg,
    kbs,
    promoteTarget,
    setPromoteTarget,
    promoteKbId,
    setPromoteKbId,
    promoteBusy,
    list,
    filtered,
    confirmDialog,
    onDelete,
    openPromote,
    onPromote,
  } = vm;

  return (
    <>
      <ResourceListLayout
        title="生成素材"
        description={MEDIA_ASSETS_PAGE_DESC}
        searchPlaceholder="搜索标题、prompt、文件名"
        search={search}
        onSearchChange={setSearch}
        loading={list.loading}
        headerAction={
          <div className="flex flex-wrap items-center gap-2">
            <select className="input-field w-auto text-sm" value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="">全部类型</option>
              <option value="image">图片</option>
              <option value="video">视频</option>
            </select>
            <select className="input-field w-auto text-sm" value={promoted} onChange={(e) => setPromoted(e.target.value as "" | "yes" | "no")}>
              <option value="">全部状态</option>
              <option value="no">未入库</option>
              <option value="yes">已入库</option>
            </select>
          </div>
        }
        footer={
          !list.loading ? (
            <ResourceListFooter page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
          ) : null
        }
      >
        {msg && <p className="mb-4 text-sm text-ink-muted">{msg}</p>}
        {filtered.length === 0 && !list.loading ? (
          <p className="text-sm text-ink-muted">暂无生成素材。在智能体中开启生成工具并生图/生视频，或在流程中使用生图/生视频节点。</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((a) => (
              <MediaAssetCard key={a.id} asset={a} kbs={kbs} onPromote={() => openPromote(a)} onDelete={() => onDelete(a)} />
            ))}
          </div>
        )}
      </ResourceListLayout>

      <MediaAssetPromoteDialog
        open={!!promoteTarget}
        kbs={kbs}
        promoteKbId={promoteKbId}
        busy={promoteBusy}
        onKbChange={setPromoteKbId}
        onClose={() => setPromoteTarget(null)}
        onConfirm={() => void onPromote()}
      />
      {confirmDialog}
    </>
  );
}
