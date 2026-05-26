"use client";

/** 画布/配置：选择图片 attachment_id（上传、最近附件、生成素材）。 */

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Attachment, MediaAsset } from "@/lib/types";

type PickerItem = {
  attachmentId: string;
  label: string;
  sublabel?: string;
};

function isImageMime(mime: string) {
  return mime.startsWith("image/");
}

type Props = {
  value: string;
  onChange: (attachmentId: string) => void;
  disabled?: boolean;
  /** 上传时 attachment purpose */
  uploadPurpose?: string;
  placeholder?: string;
};

export function AttachmentIdField({
  value,
  onChange,
  disabled,
  uploadPurpose = "flow",
  placeholder = "选择或上传图片，亦可由入边传入",
}: Props) {
  const listId = useId();
  const fileRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<PickerItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [manual, setManual] = useState(value);

  useEffect(() => {
    setManual(value);
  }, [value]);

  useEffect(() => {
    if (!value) {
      setPreviewUrl(null);
      return;
    }
    let cancelled = false;
    let blobUrl: string | null = null;
    void api.fetchAttachmentPreviewUrl(value).then((u) => {
      if (!cancelled) {
        blobUrl = u;
        setPreviewUrl(u);
      }
    });
    return () => {
      cancelled = true;
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [value]);

  const loadItems = useCallback(async () => {
    setLoading(true);
    try {
      const seen = new Set<string>();
      const next: PickerItem[] = [];

      const [attPage, assetPage] = await Promise.all([
        api.listAttachments(1, 30),
        api.listMediaAssets(1, 20, { kind: "image" }),
      ]);

      for (const a of attPage.items) {
        if (!isImageMime(a.mime_type) || seen.has(a.id)) continue;
        seen.add(a.id);
        next.push({
          attachmentId: a.id,
          label: a.filename,
          sublabel: a.purpose,
        });
      }

      for (const m of assetPage.items) {
        const id = m.attachment_id;
        if (!id || seen.has(id)) continue;
        seen.add(id);
        const att = m.attachment;
        next.push({
          attachmentId: id,
          label: m.title ?? att?.filename ?? id.slice(0, 8),
          sublabel: m.source,
        });
      }

      setItems(next);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) void loadItems();
  }, [open, loadItems]);

  const onUpload = async (files: FileList | null) => {
    if (!files?.length || uploading) return;
    setUploading(true);
    try {
      const att = await api.uploadAttachment(files[0], { purpose: uploadPurpose });
      onChange(att.id);
      setOpen(false);
      if (open) await loadItems();
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const applyManual = () => {
    onChange(manual.trim());
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <input
          className="input-field min-w-0 flex-1 font-mono text-xs"
          value={manual}
          onChange={(e) => setManual(e.target.value)}
          onBlur={applyManual}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              applyManual();
            }
          }}
          placeholder={placeholder}
          disabled={disabled}
          aria-describedby={open ? listId : undefined}
        />
        <button
          type="button"
          className="btn-sm-outline shrink-0"
          disabled={disabled}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "收起" : "选择…"}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={(e) => void onUpload(e.target.files)}
        />
        <button
          type="button"
          className="btn-sm-outline shrink-0"
          disabled={disabled || uploading}
          onClick={() => fileRef.current?.click()}
        >
          {uploading ? "上传…" : "上传"}
        </button>
        {value ? (
          <button
            type="button"
            className="btn-sm-ghost shrink-0 text-xs"
            disabled={disabled}
            onClick={() => onChange("")}
          >
            清除
          </button>
        ) : null}
      </div>

      {value && previewUrl ? (
        <img
          src={previewUrl}
          alt="已选参考图"
          className="h-16 w-16 rounded-lg object-cover ring-1 ring-line"
        />
      ) : null}

      {open ? (
        <div
          id={listId}
          className="max-h-40 overflow-y-auto rounded-lg border border-line bg-surface-muted p-2"
        >
          {loading ? (
            <p className="text-xs text-ink-muted">加载中…</p>
          ) : items.length === 0 ? (
            <p className="text-xs text-ink-faint">暂无图片附件，请先上传</p>
          ) : (
            <ul className="space-y-1">
              {items.map((item) => (
                <li key={item.attachmentId}>
                  <button
                    type="button"
                    className={`w-full rounded-md px-2 py-1.5 text-left text-xs transition hover:bg-surface ${
                      item.attachmentId === value
                        ? "bg-brand-light text-brand ring-1 ring-brand/30"
                        : "text-ink"
                    }`}
                    disabled={disabled}
                    onClick={() => {
                      onChange(item.attachmentId);
                      setManual(item.attachmentId);
                      setOpen(false);
                    }}
                  >
                    <span className="font-medium">{item.label}</span>
                    {item.sublabel ? (
                      <span className="ml-1 text-ink-faint">· {item.sublabel}</span>
                    ) : null}
                    <span className="mt-0.5 block font-mono text-[10px] text-ink-muted">
                      {item.attachmentId.slice(0, 8)}…
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
