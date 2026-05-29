"use client";

import { KbDocumentRow } from "@/features/kb/components/KbDocumentRow";
import { KbUploadZone } from "@/features/kb/components/KbUploadZone";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { KB_DOC_FILTERS } from "@/features/kb/lib/kb-detail-shared";
import type { KbDetailPageVm } from "@/features/kb/hooks/use-kb-detail-page";

export function KbDetailDocumentsTab({ vm }: { vm: KbDetailPageVm }) {
  return (
    <section className="space-y-4">
      <KbUploadZone uploading={vm.uploading} onFiles={vm.onUploadFiles} />

      <div className="rounded-xl border border-line bg-surface p-4 shadow-card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-ink">文档列表</h2>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="btn-ghost flex h-8 w-8 items-center justify-center p-0"
              aria-label="刷新"
              title="刷新"
              disabled={vm.docsRefreshing || vm.docs.loading}
              onClick={() => void vm.onRefreshDocuments()}
            >
              <svg
                className={`h-4 w-4 ${vm.docsRefreshing ? "animate-spin" : ""}`}
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
              {KB_DOC_FILTERS.map((f) => (
                <button
                  key={f.key}
                  type="button"
                  onClick={() => vm.setDocFilter(f.key)}
                  className={`rounded-full px-2.5 py-1 text-xs transition ${
                    vm.docFilter === f.key ? "bg-brand text-white" : "bg-surface-muted text-ink-muted hover:text-ink"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>
        </div>
        {vm.docFilter !== "all" ? <p className="mt-2 text-xs text-ink-faint">筛选仅作用于当前页；切换页码可查看更多。</p> : null}

        {vm.docs.loading ? (
          <ul className="mt-4 space-y-2">
            {[1, 2, 3].map((i) => (
              <li key={i} className="h-14 animate-pulse rounded-lg bg-surface-muted" />
            ))}
          </ul>
        ) : vm.docs.items.length === 0 ? (
          <p className="mt-6 text-center text-sm text-ink-muted">暂无文档。上传文件后将自动解析、分片并写入向量库。</p>
        ) : vm.filteredDocs.length === 0 ? (
          <p className="mt-6 text-center text-sm text-ink-muted">当前筛选下无文档。</p>
        ) : (
          <>
            <ul className="mt-4 space-y-2">
              {vm.filteredDocs.map((d) => (
                <KbDocumentRow
                  key={d.id}
                  doc={d}
                  statusOptions={vm.kbMeta?.document_statuses}
                  retrying={vm.retryingId === d.id}
                  expanded={vm.expandedFailId === d.id}
                  onToggleFail={() => vm.setExpandedFailId((prev) => (prev === d.id ? null : d.id))}
                  onRetry={() => void vm.onRetry(d.id)}
                  onViewChunks={() => vm.setChunksDoc(d)}
                  onDelete={() => vm.onRequestDeleteDoc(d)}
                />
              ))}
            </ul>
            <ResourceListFooter
              className="mt-4 border-t border-line pt-3"
              page={vm.docs.page}
              size={vm.docs.size}
              total={vm.docs.total}
              onPageChange={vm.docs.setPage}
              onSizeChange={vm.docs.setSize}
            />
          </>
        )}
      </div>
    </section>
  );
}
