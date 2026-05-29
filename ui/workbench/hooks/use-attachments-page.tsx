"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useAttachmentMeta } from "@/hooks/use-attachment-meta";
import { attachmentPurposeFilterOptions, attachmentPurposeUploadOptions } from "@/lib/attachment-labels";
import { filterBySearch } from "@/lib/filter-search";
import type { Attachment } from "@/lib/types";
import type { KbQuota } from "@/lib/types";

export function useAttachmentsPage() {
  const { ready } = useRequireAuth();
  const attachmentMeta = useAttachmentMeta(ready);
  const purposeFilterOptions = attachmentPurposeFilterOptions(attachmentMeta);
  const purposeUploadOptions = attachmentPurposeUploadOptions(attachmentMeta);
  const [search, setSearch] = useState("");
  const [purpose, setPurpose] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadPurpose, setUploadPurpose] = useState("general");
  const [msg, setMsg] = useState("");
  const [quota, setQuota] = useState<KbQuota | null>(null);
  const [quotaLoading, setQuotaLoading] = useState(true);

  const list = usePagedList(useCallback((p, s) => api.listAttachments(p, s, purpose ? { purpose } : undefined), [purpose]), {
    enabled: ready,
    resetKey: purpose,
  });
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const reloadQuota = useCallback(() => {
    if (!ready) return Promise.resolve();
    setQuotaLoading(true);
    return api
      .getKbQuota()
      .then(setQuota)
      .catch(() => setQuota(null))
      .finally(() => setQuotaLoading(false));
  }, [ready]);

  useEffect(() => {
    void reloadQuota();
  }, [reloadQuota, list.total]);

  const filtered = useMemo(() => filterBySearch(list.items, search, (a) => `${a.filename} ${a.purpose} ${a.mime_type}`), [list.items, search]);

  const onUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setMsg("");
    try {
      await api.uploadAttachment(file, { purpose: uploadPurpose });
      await list.reload();
      await reloadQuota();
      setMsg("上传成功");
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "上传失败");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const onDelete = (a: Attachment) => {
    requestConfirm({
      title: "删除附件",
      message: (
        <>
          确定删除附件 <span className="font-medium">{a.filename}</span>？
        </>
      ),
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deleteAttachment(a.id);
        await list.reload();
        await reloadQuota();
        setMsg("已删除");
      },
    });
  };

  return {
    attachmentMeta,
    purposeFilterOptions,
    purposeUploadOptions,
    search,
    setSearch,
    purpose,
    setPurpose,
    uploading,
    uploadPurpose,
    setUploadPurpose,
    msg,
    quota,
    quotaLoading,
    list,
    filtered,
    confirmDialog,
    onUpload,
    onDelete,
  };
}

export type AttachmentsPageVm = ReturnType<typeof useAttachmentsPage>;
