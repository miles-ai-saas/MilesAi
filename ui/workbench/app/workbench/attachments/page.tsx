"use client";

/** 附件列表（链路 §3 + §4 `useAttachmentMeta`）。 */

import { AttachmentsPageView } from "@/components/attachments/AttachmentsPageView";
import { useAttachmentsPage } from "@/hooks/use-attachments-page";

export default function AttachmentsPage() {
  const vm = useAttachmentsPage();
  return <AttachmentsPageView vm={vm} />;
}
