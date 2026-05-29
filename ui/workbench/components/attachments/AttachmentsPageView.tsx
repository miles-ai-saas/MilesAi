"use client";

import { KbQuotaBar } from "@/components/kb/KbQuotaBar";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import type { AttachmentsPageVm } from "@/hooks/use-attachments-page";
import { attachmentPurposeLabel } from "@/lib/attachment-labels";
import { ATTACHMENTS_PAGE_DESC, formatAttachmentBytes } from "@/lib/attachments-page-shared";
import { KB_UPLOAD_ACCEPT } from "@/lib/upload-accept";

export function AttachmentsTable({ vm }: { vm: AttachmentsPageVm }) {
  const { filtered, attachmentMeta, onDelete } = vm;

  return (
    <div className="overflow-x-auto rounded-lg border border-line">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-line bg-surface-muted text-xs text-ink-muted">
          <tr>
            <th className="px-4 py-2 font-medium">文件名</th>
            <th className="px-4 py-2 font-medium">用途</th>
            <th className="px-4 py-2 font-medium">大小</th>
            <th className="px-4 py-2 font-medium">类型</th>
            <th className="px-4 py-2 font-medium">上传时间</th>
            <th className="px-4 py-2 font-medium" />
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {filtered.map((a) => (
            <tr key={a.id} className="hover:bg-surface-muted/50">
              <td className="max-w-[16rem] truncate px-4 py-2 font-medium">{a.filename}</td>
              <td className="px-4 py-2 text-ink-muted">{attachmentPurposeLabel(a.purpose, attachmentMeta)}</td>
              <td className="px-4 py-2 text-ink-muted">{formatAttachmentBytes(a.file_size)}</td>
              <td className="px-4 py-2 text-xs text-ink-faint">{a.mime_type}</td>
              <td className="px-4 py-2 text-xs text-ink-faint">{new Date(a.created_at).toLocaleString()}</td>
              <td className="px-4 py-2 text-right">
                <button type="button" className="text-xs text-red-600 hover:underline" onClick={() => onDelete(a)}>
                  删除
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AttachmentsPageView({ vm }: { vm: AttachmentsPageVm }) {
  const {
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
  } = vm;

  return (
    <>
      <ResourceListLayout
        title="附件"
        description={ATTACHMENTS_PAGE_DESC}
        searchPlaceholder="搜索文件名"
        search={search}
        onSearchChange={setSearch}
        loading={list.loading}
        headerAction={
          <div className="flex flex-wrap items-center gap-3">
            <KbQuotaBar quota={quota} loading={quotaLoading} variant="inline" />
            <div className="flex flex-wrap items-center gap-2">
              <select className="input-field w-auto text-sm" value={purpose} onChange={(e) => setPurpose(e.target.value)}>
                {purposeFilterOptions.map((o) => (
                  <option key={o.value || "all"} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <select className="input-field w-auto text-sm" value={uploadPurpose} onChange={(e) => setUploadPurpose(e.target.value)} title="上传用途">
                {purposeUploadOptions.map((o) => (
                  <option key={o.value} value={o.value}>
                    上传为：{o.label}
                  </option>
                ))}
              </select>
              <label className="btn-primary cursor-pointer text-sm">
                {uploading ? "上传中…" : "上传附件"}
                <input type="file" className="hidden" accept={KB_UPLOAD_ACCEPT} onChange={onUpload} disabled={uploading} />
              </label>
            </div>
          </div>
        }
        footer={
          !list.loading ? (
            <ResourceListFooter page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
          ) : null
        }
      >
        {msg && <p className="mb-4 text-sm text-ink-muted">{msg}</p>}
        {filtered.length === 0 && !list.loading ? (
          <p className="text-sm text-ink-muted">暂无附件，点击「上传附件」添加。</p>
        ) : (
          <AttachmentsTable vm={vm} />
        )}
      </ResourceListLayout>
      {confirmDialog}
    </>
  );
}
