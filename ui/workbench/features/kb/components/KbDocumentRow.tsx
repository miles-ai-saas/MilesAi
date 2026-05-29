"use client";

import { canRetryDocument, documentStatusLabel, documentStatusTone, isDocumentFailed, isDocumentProcessing, type DocumentStatusTone } from "@/lib/document-status";
import { formatFileSize } from "@/lib/format-bytes";
import type { EnumOption } from "@/lib/enum-meta";
import type { Document } from "@/lib/types";

const DOC_STATUS_TONE_CLASS: Record<DocumentStatusTone, string> = {
  success: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  progress: "bg-sky-50 text-sky-800 ring-sky-200",
  error: "bg-red-50 text-red-800 ring-red-200",
  neutral: "bg-surface-muted text-ink-muted ring-line",
};

function kbFileIcon(filename: string): string {
  const ext = filename.includes(".") ? filename.slice(filename.lastIndexOf(".")).toLowerCase() : "";
  if ([".pdf"].includes(ext)) return "PDF";
  if ([".docx", ".doc"].includes(ext)) return "DOC";
  if ([".pptx", ".ppt"].includes(ext)) return "PPT";
  if ([".xlsx", ".xls"].includes(ext)) return "XLS";
  if ([".md", ".markdown", ".txt"].includes(ext)) return "TXT";
  if ([".jpg", ".jpeg", ".png", ".webp"].includes(ext)) return "IMG";
  if ([".mp3", ".wav", ".m4a", ".ogg", ".webm"].includes(ext)) return "AUD";
  if ([".html", ".htm"].includes(ext)) return "WEB";
  return "FILE";
}

function DocumentStatusBadge({ status, pulse, statusOptions }: { status: string; pulse?: boolean; statusOptions?: EnumOption[] }) {
  const tone = documentStatusTone(status);
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${DOC_STATUS_TONE_CLASS[tone]} ${
        pulse && tone === "progress" ? "animate-pulse" : ""
      }`}
    >
      {tone === "progress" && <span className="inline-block h-1.5 w-1.5 rounded-full bg-current" aria-hidden />}
      {documentStatusLabel(status, statusOptions)}
    </span>
  );
}

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
