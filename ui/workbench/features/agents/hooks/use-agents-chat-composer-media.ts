"use client";

import { useCallback, useMemo, useState } from "react";
import type { PendingChatMedia } from "@/features/agents/components/AgentChatComposer";
import { api } from "@/lib/api";
import type { ChatMessage, ChatMessageMedia } from "@/lib/chat-sessions";
import { CHAT_ATTACHMENT_MAX_COUNT, filterChatUploadFiles } from "@/lib/chat-attachments";
import { lastUserMessageMedia } from "@/lib/chat-media-forward";

type Params = {
  messages: ChatMessage[];
  carryForwardMedia: boolean;
};

export function useAgentsChatComposerMedia({ messages, carryForwardMedia }: Params) {
  const [pendingMedia, setPendingMedia] = useState<PendingChatMedia[]>([]);
  const [uploadingMedia, setUploadingMedia] = useState(false);

  const carriedMedia = useMemo((): ChatMessageMedia[] => {
    if (pendingMedia.length > 0 || !carryForwardMedia) return [];
    return lastUserMessageMedia(messages);
  }, [carryForwardMedia, messages, pendingMedia.length]);

  const onPickAttachments = async (files: FileList | null) => {
    if (!files?.length || uploadingMedia) return;
    const picked = filterChatUploadFiles(files);
    if (!picked.length) {
      window.alert("当前仅支持上传图片（JPEG / PNG / WebP / GIF）");
      return;
    }
    setUploadingMedia(true);
    try {
      const next: PendingChatMedia[] = [];
      for (const file of picked) {
        const att = await api.uploadAttachment(file, { purpose: "chat" });
        const local_preview = URL.createObjectURL(file);
        next.push({
          attachment_id: att.id,
          filename: att.filename,
          preview_url: local_preview,
          local_preview,
        });
      }
      if (next.length) {
        setPendingMedia((prev) => [...prev, ...next].slice(0, CHAT_ATTACHMENT_MAX_COUNT));
      }
    } catch (e) {
      const err = e instanceof Error ? e.message : "附件上传失败";
      window.alert(err);
    } finally {
      setUploadingMedia(false);
    }
  };

  const removePendingMedia = (attachmentId: string) => {
    setPendingMedia((prev) => {
      const item = prev.find((p) => p.attachment_id === attachmentId);
      if (item?.local_preview) URL.revokeObjectURL(item.local_preview);
      return prev.filter((p) => p.attachment_id !== attachmentId);
    });
  };

  const clearPendingMedia = useCallback(() => {
    setPendingMedia([]);
  }, []);

  return {
    pendingMedia,
    setPendingMedia,
    uploadingMedia,
    carriedMedia,
    onPickAttachments,
    removePendingMedia,
    clearPendingMedia,
  };
}
