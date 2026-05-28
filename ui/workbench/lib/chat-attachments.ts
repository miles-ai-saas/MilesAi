/**
 * 对话工作台附件上传约定（识图等多模态）。
 * 扩展新格式时在此增加 picker，并在上传校验 / 预览组件中补齐。
 */

export type ChatAttachmentKind = "image";

export type ChatAttachmentPicker = {
  kind: ChatAttachmentKind;
  /** input accept，如 image/* 或具体 MIME 列表 */
  accept: string;
  label: string;
  maxCount: number;
};

/** 当前仅开放图片；后续可增加 document / audio 等 */
export const CHAT_ATTACHMENT_PICKERS: ChatAttachmentPicker[] = [
  {
    kind: "image",
    accept: "image/jpeg,image/png,image/webp,image/gif",
    label: "图片",
    maxCount: 4,
  },
];

export const CHAT_ATTACHMENT_ACCEPT = CHAT_ATTACHMENT_PICKERS.map((p) => p.accept).join(",");

export const CHAT_ATTACHMENT_MAX_COUNT = Math.max(...CHAT_ATTACHMENT_PICKERS.map((p) => p.maxCount));

export function filterChatUploadFiles(files: FileList | File[]): File[] {
  const list = Array.from(files);
  const imagePicker = CHAT_ATTACHMENT_PICKERS.find((p) => p.kind === "image");
  if (!imagePicker) return [];
  return list.filter((f) => {
    if (f.type.startsWith("image/")) return true;
    const ext = f.name.split(".").pop()?.toLowerCase();
    return ext === "jpg" || ext === "jpeg" || ext === "png" || ext === "webp" || ext === "gif";
  });
}
