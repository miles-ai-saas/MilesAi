"use client";

/**
 * 智能体对话输入区：附件在框内左下，发送在右下；统一白底无分栏。
 */

import { useEffect, useRef, useState } from "react";
import type { ChatMessageMedia, PendingChatMedia } from "@/features/agents/lib/chat-sessions";
import { CHAT_ATTACHMENT_ACCEPT } from "@/lib/chat-attachments";
import { api } from "@/lib/api";

type Props = {
  query: string;
  onQueryChange: (value: string) => void;
  onSend: () => void;
  onPickFiles: (files: FileList | null) => void;
  pendingMedia: PendingChatMedia[];
  carriedMedia: ChatMessageMedia[];
  onRemovePending: (attachmentId: string) => void;
  carryForwardHint?: string;
  disabled?: boolean;
  sendDisabled?: boolean;
  uploadingMedia?: boolean;
  chatting?: boolean;
  sendLabel?: string;
  placeholder?: string;
  /** 生图数量（1–4） */
  imageN?: number;
  onImageNChange?: (n: number) => void;
  /** 生视频时长（秒，1–15） */
  videoDuration?: number;
  onVideoDurationChange?: (d: number) => void;
};

function AttachIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
    </svg>
  );
}

/** 沿用附图：消息里的 preview_url 常为 blob（刷新后失效），统一走鉴权 content API。 */
function CarriedAttachmentThumb({ attachmentId, filename, previewUrl }: { attachmentId: string; filename?: string; previewUrl?: string }) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    const isBlob = previewUrl?.startsWith("blob:");
    if (previewUrl && !isBlob) {
      setSrc(previewUrl);
      return;
    }
    void api.fetchAttachmentPreviewUrl(attachmentId).then((u) => {
      if (!cancelled) {
        objectUrl = u;
        setSrc(u);
      } else {
        URL.revokeObjectURL(u);
      }
    });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [attachmentId, previewUrl]);

  return (
    <div
      className="h-12 w-12 overflow-hidden rounded-md ring-1 ring-dashed ring-brand/35"
      title={filename ?? "上一轮附图"}
    >
      {src ? (
        <img src={src} alt={filename ?? "上一轮附图"} className="h-full w-full object-cover opacity-90" />
      ) : (
        <div className="flex h-full w-full items-center justify-center bg-surface-muted text-[10px] text-ink-faint">…</div>
      )}
    </div>
  );
}

export function AgentChatComposer({
  query,
  onQueryChange,
  onSend,
  onPickFiles,
  pendingMedia,
  carriedMedia,
  onRemovePending,
  carryForwardHint,
  disabled = false,
  sendDisabled = false,
  uploadingMedia = false,
  chatting = false,
  sendLabel = "发送",
  placeholder = "输入消息，Enter 发送，Shift+Enter 换行",
  imageN = 1,
  onImageNChange,
  videoDuration = 5,
  onVideoDurationChange,
}: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const attachDisabled = disabled || uploadingMedia || chatting;

  return (
    <div className="w-full space-y-2">
      {(pendingMedia.length > 0 || carriedMedia.length > 0) && (
        <div className="space-y-1.5 px-0.5">
          {carryForwardHint ? <p className="text-[11px] text-ink-muted">{carryForwardHint}</p> : null}
          <div className="flex flex-wrap gap-1.5">
            {pendingMedia.map((m) => (
              <div key={m.attachment_id} className="relative">
                <img src={m.local_preview} alt={m.filename ?? "待发送"} className="h-12 w-12 rounded-md object-cover ring-1 ring-line" />
                <button
                  type="button"
                  className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-ink text-[10px] text-surface"
                  aria-label="移除附件"
                  onClick={() => onRemovePending(m.attachment_id)}
                >
                  ×
                </button>
              </div>
            ))}
            {carriedMedia.map((m) => (
              <CarriedAttachmentThumb
                key={`carry-${m.attachment_id}`}
                attachmentId={m.attachment_id}
                filename={m.filename}
                previewUrl={m.preview_url}
              />
            ))}
          </div>
        </div>
      )}

      <div
        className={[
          "relative overflow-hidden rounded-2xl border border-line bg-surface shadow-sm",
          "transition-[box-shadow,border-color] focus-within:border-brand/35 focus-within:shadow-md focus-within:ring-2 focus-within:ring-brand/10",
        ].join(" ")}
      >
        <textarea
          className="block w-full resize-none border-0 bg-transparent px-4 pb-11 pt-3.5 text-sm leading-relaxed text-ink outline-none placeholder:text-ink-faint disabled:cursor-not-allowed disabled:opacity-50 min-h-[72px] max-h-[160px]"
          rows={2}
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSend();
            }
          }}
          placeholder={placeholder}
          disabled={disabled}
          aria-label="对话输入"
        />

        <input
          ref={fileInputRef}
          type="file"
          accept={CHAT_ATTACHMENT_ACCEPT}
          multiple
          className="hidden"
          onChange={(e) => {
            onPickFiles(e.target.files);
            e.target.value = "";
          }}
        />

        <div className="absolute bottom-2 left-2 flex items-center gap-1">
          <button
            type="button"
            className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-muted transition hover:bg-brand-light/80 hover:text-brand disabled:pointer-events-none disabled:opacity-40"
            disabled={attachDisabled}
            title={uploadingMedia ? "上传中…" : "添加附件（当前支持图片）"}
            aria-label="添加附件"
            onClick={() => fileInputRef.current?.click()}
          >
            {uploadingMedia ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand border-t-transparent" />
            ) : (
              <AttachIcon className="h-[18px] w-[18px]" />
            )}
          </button>

          {onImageNChange != null && (
            <div className="flex items-center rounded-full border border-line/60 px-1.5 py-0.5 text-[11px]">
              <button
                type="button"
                className="flex h-5 w-5 items-center justify-center rounded-full text-ink-muted transition hover:bg-surface-muted hover:text-ink disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-ink-muted"
                disabled={imageN <= 1 || chatting}
                onClick={() => onImageNChange(imageN - 1)}
                aria-label="减少图片数量"
              >
                <svg className="h-2.5 w-2.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
                  <path d="M4 8h8" />
                </svg>
              </button>
              <span
                className={`min-w-[1.2em] text-center text-xs font-semibold tabular-nums ${imageN >= 3 ? "text-amber-600" : imageN > 1 ? "text-brand" : "text-ink"}`}
              >
                {imageN}
              </span>
              <button
                type="button"
                className="flex h-5 w-5 items-center justify-center rounded-full text-ink-muted transition hover:bg-surface-muted hover:text-ink disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-ink-muted"
                disabled={imageN >= 4 || chatting}
                onClick={() => onImageNChange(imageN + 1)}
                aria-label="增加图片数量"
              >
                <svg className="h-2.5 w-2.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
                  <path d="M4 8h8M8 4v8" />
                </svg>
              </button>
            </div>
          )}

          {onVideoDurationChange != null && (
            <div className="flex items-center rounded-full border border-line/60 px-1.5 py-0.5 text-[11px]">
              <div className="relative">
                <select
                  className="appearance-none rounded bg-transparent py-px pl-0.5 pr-4 text-xs font-semibold text-ink outline-none disabled:opacity-40 cursor-pointer"
                  value={videoDuration}
                  disabled={chatting}
                  onChange={(e) => onVideoDurationChange(Number(e.target.value))}
                  aria-label="生视频时长"
                >
                  {[3, 5, 10, 15].map((d) => (
                    <option key={d} value={d}>
                      {d}s
                    </option>
                  ))}
                </select>
                <svg className="pointer-events-none absolute right-0.5 top-1/2 h-2 w-2 -translate-y-1/2 text-ink-muted" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
                  <path d="M4 6l4 4 4-4" />
                </svg>
              </div>
            </div>
          )}
        </div>

        <div className="absolute bottom-2 right-2 flex items-center gap-1.5">
          {imageN > 1 && (
            <span className="mr-0.5 rounded-full bg-brand-light px-1.5 py-px text-[10px] font-medium text-brand-dark">
              {imageN} 张
            </span>
          )}
          <button
            type="button"
            onClick={onSend}
            disabled={sendDisabled || attachDisabled}
            className="btn-primary px-4 py-1.5 text-sm shadow-sm disabled:opacity-45"
          >
            {chatting ? sendLabel : "发送"}
          </button>
        </div>
      </div>
    </div>
  );
}
