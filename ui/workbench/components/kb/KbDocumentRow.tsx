"use client";

import { DocumentStatusBadge } from "@/components/kb/DocumentStatusBadge";
import { canRetryDocument, isDocumentFailed, isDocumentProcessing } from "@/lib/document-status";
import { formatFileSize } from "@/lib/format-bytes";
import { kbFileIcon } from "@/lib/kb-file-icon";
import type { EnumOption } from "@/lib/enum-meta";
import type { Document } from "@/lib/types";

export function KbDocumentRow({
  doc,
  statusOptions,
  retrying,
  expanded,
  onToggleFail,
  onRetry,
  onViewChunks,
  onDelete,
}: {
  doc: Document;
  statusOptions?: EnumOption[];
  retrying: boolean;
  expanded: boolean;
  onToggleFail: () => void;
  onRetry: () => void;
  onViewChunks: () => void;
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
          <DocumentStatusBadge status={doc.status} pulse={isDocumentProcessing(doc.status)} statusOptions={statusOptions} />
        </div>
        <p className="mt-0.5 text-xs text-ink-faint">
          {formatFileSize(doc.file_size)} · {new Date(doc.created_at).toLocaleString()}
          {doc.status === "ready" && doc.chunk_count != null && doc.chunk_count > 0 && <> · {doc.chunk_count} 个分片</>}
        </p>
        {(hasFail || isDocumentFailed(doc.status)) && (
          <div className="mt-2">
            <button type="button" className="text-left text-xs text-red-700 hover:underline" onClick={onToggleFail}>
              {expanded ? "收起失败原因" : "查看失败原因"}
            </button>
            {expanded && <p className="mt-1 whitespace-pre-wrap rounded-md bg-red-50 px-2 py-1.5 text-xs text-red-900">{doc.fail_reason}</p>}
          </div>
        )}
      </div>
      <div className="flex shrink-0 flex-col items-end justify-center gap-1 sm:flex-row sm:items-center">
        {doc.status === "ready" && (doc.chunk_count ?? 0) > 0 && (
          <button type="button" className="btn-ghost px-2 py-1 text-xs" onClick={onViewChunks}>
            查看分片
          </button>
        )}
        {canRetryDocument(doc.status) && (
          <button type="button" className="btn-primary px-2 py-1 text-xs" disabled={retrying} onClick={onRetry}>
            {retrying ? "提交中…" : "重试入库"}
          </button>
        )}
        <button type="button" className="btn-ghost px-2 py-1 text-xs text-red-600 hover:bg-red-50" onClick={onDelete}>
          删除
        </button>
      </div>
    </li>
  );
}
