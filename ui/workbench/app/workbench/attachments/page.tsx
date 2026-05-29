"use client";

/** 附件列表（链路 §3 + §4 `useAttachmentMeta`）。 */

import { AttachmentsPageView, useAttachmentsPage } from "@/features/attachments";

export default function AttachmentsPage() {
  const vm = useAttachmentsPage();
  return <AttachmentsPageView vm={vm} />;
}
