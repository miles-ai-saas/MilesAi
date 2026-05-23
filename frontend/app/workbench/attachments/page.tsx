"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { KbQuotaBar } from "@/components/kb/KbQuotaBar";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { filterBySearch } from "@/lib/filter-search";
import { ATTACHMENT_PURPOSE_LABEL } from "@/lib/kb-labels";
import { KB_UPLOAD_ACCEPT } from "@/lib/upload-accept";
import type { Attachment, KbQuota } from "@/lib/types";

const PURPOSE_OPTIONS = [
  { value: "", label: "全部用途" },
  { value: "general", label: "通用" },
  { value: "chat", label: "对话" },
  { value: "agent", label: "智能体" },
  { value: "flow", label: "流程" },
];

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

export default function AttachmentsPage() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [purpose, setPurpose] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadPurpose, setUploadPurpose] = useState("general");
  const [msg, setMsg] = useState("");
  const [quota, setQuota] = useState<KbQuota | null>(null);
  const [quotaLoading, setQuotaLoading] = useState(true);

  const list = usePagedList(
    useCallback(
      (p, s) => api.listAttachments(p, s, purpose ? { purpose } : undefined),
      [purpose],
    ),
    { enabled: ready, resetKey: purpose },
  );
  const { requestConfirm, confirmDialog } = useConfirmAction();

  useEffect(() => {
    if (!ready) return;
    setQuotaLoading(true);
    api
      .getKbQuota()
      .then(setQuota)
      .catch(() => setQuota(null))
      .finally(() => setQuotaLoading(false));
  }, [ready, list.total]);

  const filtered = useMemo(
    () =>
      filterBySearch(list.items, search, (a) => `${a.filename} ${a.purpose} ${a.mime_type}`),
    [list.items, search],
  );

  const onUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setMsg("");
    try {
      await api.uploadAttachment(file, { purpose: uploadPurpose });
      await list.reload();
      const q = await api.getKbQuota();
      setQuota(q);
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
        const q = await api.getKbQuota();
        setQuota(q);
        setMsg("已删除");
      },
    });
  };

  return (
    <>
      <ResourceListLayout
        title="附件"
        description="租户级通用文件存储，可用于对话、智能体等场景；占用与知识库文档合计的存储配额。"
        searchPlaceholder="搜索文件名"
        search={search}
        onSearchChange={setSearch}
        loading={list.loading}
        headerAction={
          <div className="flex flex-wrap items-center gap-3">
            <KbQuotaBar quota={quota} loading={quotaLoading} variant="inline" />
            <div className="flex flex-wrap items-center gap-2">
            <select
              className="input-field w-auto text-sm"
              value={purpose}
              onChange={(e) => setPurpose(e.target.value)}
            >
              {PURPOSE_OPTIONS.map((o) => (
                <option key={o.value || "all"} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <select
              className="input-field w-auto text-sm"
              value={uploadPurpose}
              onChange={(e) => setUploadPurpose(e.target.value)}
              title="上传用途"
            >
              {PURPOSE_OPTIONS.filter((o) => o.value).map((o) => (
                <option key={o.value} value={o.value}>
                  上传为：{o.label}
                </option>
              ))}
            </select>
            <label className="btn-primary cursor-pointer text-sm">
              {uploading ? "上传中…" : "上传附件"}
              <input
                type="file"
                className="hidden"
                accept={KB_UPLOAD_ACCEPT}
                onChange={onUpload}
                disabled={uploading}
              />
            </label>
            </div>
          </div>
        }
        footer={
          !list.loading ? (
            <ResourceListFooter
              page={list.page}
              size={list.size}
              total={list.total}
              onPageChange={list.setPage}
            />
          ) : null
        }
      >
        {msg && <p className="mb-4 text-sm text-ink-muted">{msg}</p>}
        {filtered.length === 0 && !list.loading ? (
          <p className="text-sm text-ink-muted">暂无附件，点击「上传附件」添加。</p>
        ) : (
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
                    <td className="px-4 py-2 text-ink-muted">
                      {ATTACHMENT_PURPOSE_LABEL[a.purpose] ?? a.purpose}
                    </td>
                    <td className="px-4 py-2 text-ink-muted">{formatBytes(a.file_size)}</td>
                    <td className="px-4 py-2 text-xs text-ink-faint">{a.mime_type}</td>
                    <td className="px-4 py-2 text-xs text-ink-faint">
                      {new Date(a.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <button
                        type="button"
                        className="text-xs text-red-600 hover:underline"
                        onClick={() => onDelete(a)}
                      >
                        删除
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </ResourceListLayout>
      {confirmDialog}
    </>
  );
}
