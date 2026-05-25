"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { usePagedList } from "@/hooks/use-paged-list";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { needsPagination } from "@/lib/pagination";
import type { Document, DocumentChunk } from "@/lib/types";

const CHUNK_PAGE_SIZE = 20;
const PREVIEW_LEN = 280;

type Props = {
  kbId: string;
  doc: Document | null;
  open: boolean;
  onClose: () => void;
};

function ChunkItem({ chunk }: { chunk: DocumentChunk }) {
  const [expanded, setExpanded] = useState(false);
  const long = chunk.content.length > PREVIEW_LEN;
  const shown =
    expanded || !long ? chunk.content : `${chunk.content.slice(0, PREVIEW_LEN)}…`;

  return (
    <li className="rounded-lg border border-line bg-surface-muted/30 px-3 py-3">
      <div className="flex flex-wrap items-center gap-2 text-xs text-ink-faint">
        <span className="rounded bg-surface px-1.5 py-0.5 font-medium text-ink">
          #{chunk.chunk_index + 1}
        </span>
        {chunk.page_no != null && chunk.page_no > 0 && (
          <span>第 {chunk.page_no} 页</span>
        )}
        <span>{chunk.content.length} 字</span>
      </div>
      <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-ink">{shown}</p>
      {long && (
        <button
          type="button"
          className="mt-2 text-xs text-brand hover:underline"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? "收起" : "展开全文"}
        </button>
      )}
    </li>
  );
}

export function DocumentChunksDrawer({ kbId, doc, open, onClose }: Props) {
  const [expandedReset, setExpandedReset] = useState(0);

  const fetcher = useCallback(
    (page: number, size: number) => {
      if (!doc) return Promise.resolve({ items: [], total: 0, page: 1, size });
      return api.listDocumentChunks(kbId, doc.id, page, size);
    },
    [kbId, doc],
  );

  const chunks = usePagedList(fetcher, {
    enabled: open && !!doc,
    resetKey: doc ? `${doc.id}-${expandedReset}` : "",
    pageSize: CHUNK_PAGE_SIZE,
  });

  useEffect(() => {
    if (open && doc) setExpandedReset((n) => n + 1);
  }, [open, doc?.id]);

  if (!doc) return null;

  return (
    <ResourceDialog
      open={open}
      title="文档分片"
      description={doc.filename}
      onClose={onClose}
      size="lg"
      footer={
        needsPagination(chunks.total, CHUNK_PAGE_SIZE) ? (
          <ResourceListFooter
            page={chunks.page}
            size={chunks.size}
            total={chunks.total}
            onPageChange={chunks.setPage}
          />
        ) : undefined
      }
    >
      <p className="text-xs text-ink-muted">
        共 {doc.chunk_count ?? chunks.total} 个分片，按入库顺序展示（chunk_index）。
      </p>
      {chunks.loading ? (
        <ul className="mt-4 space-y-2">
          {[1, 2, 3].map((i) => (
            <li key={i} className="h-20 animate-pulse rounded-lg bg-surface-muted" />
          ))}
        </ul>
      ) : chunks.error ? (
        <p className="mt-4 text-sm text-red-700">{chunks.error}</p>
      ) : chunks.items.length === 0 ? (
        <p className="mt-6 text-center text-sm text-ink-muted">暂无分片数据。</p>
      ) : (
        <ul className="mt-4 space-y-3">
          {chunks.items.map((c) => (
            <ChunkItem key={c.id} chunk={c} />
          ))}
        </ul>
      )}
    </ResourceDialog>
  );
}
