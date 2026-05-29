"use client";

import { useRef, useState } from "react";
import { api } from "@/lib/api";
import type { FlowRunPendingMedia } from "@/lib/flow-run-panel-shared";

export function useFlowRunPanelMedia(pendingMedia: FlowRunPendingMedia[], onPendingMediaChange?: (items: FlowRunPendingMedia[]) => void) {
  const [uploadingMedia, setUploadingMedia] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const onPickImages = async (files: FileList | null) => {
    if (!files?.length || !onPendingMediaChange || uploadingMedia) return;
    setUploadingMedia(true);
    try {
      const next: FlowRunPendingMedia[] = [];
      for (const file of Array.from(files)) {
        if (!file.type.startsWith("image/")) continue;
        const att = await api.uploadAttachment(file, { purpose: "flow" });
        next.push({
          attachment_id: att.id,
          filename: att.filename,
          local_preview: URL.createObjectURL(file),
        });
      }
      if (next.length) {
        onPendingMediaChange([...pendingMedia, ...next].slice(0, 4));
      }
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "图片上传失败");
    } finally {
      setUploadingMedia(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const removePending = (id: string) => {
    if (!onPendingMediaChange) return;
    const item = pendingMedia.find((p) => p.attachment_id === id);
    if (item?.local_preview) URL.revokeObjectURL(item.local_preview);
    onPendingMediaChange(pendingMedia.filter((p) => p.attachment_id !== id));
  };

  return { uploadingMedia, fileInputRef, onPickImages, removePending };
}
