"use client";

/** 文档上传区（链路 §8）：单文件或批量上传。 */

import { useCallback, useState } from "react";
import { KB_UPLOAD_ACCEPT, KB_UPLOAD_HINT } from "@/lib/upload-accept";

type Props = {
  uploading: boolean;
  onFiles: (files: File[]) => void;
};

export function KbUploadZone({ uploading, onFiles }: Props) {
  const [dragOver, setDragOver] = useState(false);

  const pick = useCallback(
    (list: FileList | null | undefined) => {
      if (!list?.length || uploading) return;
      onFiles(Array.from(list));
    },
    [onFiles, uploading],
  );

  return (
    <div
      className={`relative mt-4 rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors ${
        dragOver ? "border-brand bg-brand/5" : "border-line bg-surface-muted/30 hover:border-brand/40"
      } ${uploading ? "pointer-events-none opacity-60" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        pick(e.dataTransfer.files);
      }}
    >
      <p className="text-sm font-medium text-ink">{uploading ? "正在上传…" : "拖拽文件到此处，或点击选择（可多选）"}</p>
      <p className="mt-2 text-xs text-ink-faint">{KB_UPLOAD_HINT} · 单次最多 20 个</p>
      <label className="btn-primary mt-4 inline-flex cursor-pointer text-sm">
        {uploading ? "上传中…" : "选择文件"}
        <input type="file" className="hidden" accept={KB_UPLOAD_ACCEPT} multiple disabled={uploading} onChange={(e) => pick(e.target.files)} />
      </label>
    </div>
  );
}
