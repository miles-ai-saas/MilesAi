"use client";

import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { KbQuotaBar } from "@/features/kb/components/KbQuotaBar";
import type { KbPageVm } from "@/features/kb/hooks/use-kb-page";
import { DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE } from "@/features/kb/hooks/use-kb-list";
import { retrievalModeLabel } from "@/features/kb/lib/kb-labels";

const KB_PAGE_DESC = "管理企业知识库与文档，为智能体 RAG 检索与流程节点提供知识来源。";

export function KbCatalogView({ vm }: { vm: KbPageVm }) {
  const { list, search, setSearch, quota, quotaLoading, filtered, kbMeta, router, openCreate, openEdit, onDelete } = vm;

  return (
    <ResourceListLayout
      title="知识库"
      description={KB_PAGE_DESC}
      searchPlaceholder="搜索知识库名称"
      search={search}
      onSearchChange={setSearch}
      headerAction={<KbQuotaBar quota={quota} loading={quotaLoading} variant="inline" />}
      loading={list.loading}
      footer={
        !list.loading ? (
          <ResourceListFooter page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
        ) : null
      }
    >
      <AddResourceCard label="添加新知识库" hint="创建知识库并上传文档" onClick={openCreate} />
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
              <span className="rounded bg-surface-muted px-1.5 py-0.5 text-[11px]">{kb.embedding_model_name ?? "向量化"}</span>
              <span className="rounded bg-surface-muted px-1.5 py-0.5 text-[11px]">{kb.embedding_dimension} 维</span>
              <span className="rounded bg-brand/10 px-1.5 py-0.5 text-[11px] text-brand">
                {retrievalModeLabel(kb.retrieval_mode, kbMeta?.retrieval_modes)}
              </span>
              {kb.rerank_model_name ? <span className="rounded bg-surface-muted px-1.5 py-0.5 text-[11px]">重排 {kb.rerank_model_name}</span> : null}
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
  );
}
