"use client";

import { useCallback, useState } from "react";
import { KB_UPLOAD_ACCEPT, KB_UPLOAD_HINT } from "@/lib/upload-accept";

type Props = {
  uploading: boolean;
  onFile: (file: File) => void;
};

export function KbUploadZone({ uploading, onFile }: Props) {
  const [dragOver, setDragOver] = useState(false);

  const pick = useCallback(
    (file: File | undefined) => {
      if (!file || uploading) return;
      onFile(file);
    },
    [onFile, uploading],
  );

  return (
    <div
      className={`relative mt-4 rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors ${
        dragOver
          ? "border-brand bg-brand/5"
          : "border-line bg-surface-muted/30 hover:border-brand/40"
      } ${uploading ? "pointer-events-none opacity-60" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        pick(e.dataTransfer.files[0]);
      }}
    >
      <p className="text-sm font-medium text-ink">
        {uploading ? "正在上传…" : "拖拽文件到此处，或点击选择"}
      </p>
      <p className="mt-2 text-xs text-ink-faint">{KB_UPLOAD_HINT}</p>
      <label className="btn-primary mt-4 inline-flex cursor-pointer text-sm">
        {uploading ? "上传中…" : "选择文件"}
        <input
          type="file"
          className="hidden"
          accept={KB_UPLOAD_ACCEPT}
          disabled={uploading}
          onChange={(e) => pick(e.target.files?.[0])}
        />
      </label>
    </div>
  );
}
