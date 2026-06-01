"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BizDeliverable } from "@/lib/types";
import { DELIV_STATUS_LABELS, DELIV_TYPE_LABELS } from "@/features/projects/lib/biz-labels";
import type { ProjectDetailPageVm } from "@/features/projects/hooks/use-project-detail-page";

export function ProjectDeliverablesTab({ vm }: { vm: ProjectDetailPageVm }) {
  const { projectId, deliverables, loadDeliverables } = vm;
  const [name, setName] = useState("");
  const [type, setType] = useState("document");
  const [version, setVersion] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [uploadingId, setUploadingId] = useState<string | null>(null);
  const [actionId, setActionId] = useState<string | null>(null);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      let attachmentId: string | undefined;
      if (file) {
        const att = await api.uploadAttachment(file, { purpose: "deliverable", resource_type: "biz_project", resource_id: projectId });
        attachmentId = att.id;
      }
      await api.createDeliverable({
        project_id: projectId,
        name: name.trim(),
        type,
        version: version.trim() || undefined,
        attachment_id: attachmentId,
      });
      setName("");
      setType("document");
      setVersion("");
      setFile(null);
      await loadDeliverables();
    } finally {
      setSaving(false);
    }
  };

  const handleAttachFile = async (deliverableId: string, selected: File | null) => {
    if (!selected) return;
    setUploadingId(deliverableId);
    try {
      const att = await api.uploadAttachment(selected, { purpose: "deliverable", resource_type: "biz_project", resource_id: projectId });
      await api.updateDeliverable(deliverableId, { attachment_id: att.id });
      await loadDeliverables();
    } finally {
      setUploadingId(null);
    }
  };

  return (
    <div className="mt-4 space-y-4">
      <form onSubmit={handleAdd} className="card flex flex-wrap items-end gap-3 p-4">
        <label className="flex-1">
          <span className="text-xs text-ink-muted">名称</span>
          <input className="input-field mt-1 w-full text-sm" value={name} onChange={(e) => setName(e.target.value)} placeholder="交付物名称" required />
        </label>
        <label>
          <span className="text-xs text-ink-muted">类型</span>
          <select className="input-field mt-1 text-sm" value={type} onChange={(e) => setType(e.target.value)}>
            {Object.entries(DELIV_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label>
          <span className="text-xs text-ink-muted">版本</span>
          <input className="input-field mt-1 w-24 text-sm" value={version} onChange={(e) => setVersion(e.target.value)} placeholder="v1.0" />
        </label>
        <label>
          <span className="text-xs text-ink-muted">附件</span>
          <input type="file" className="mt-1 block w-full text-xs text-ink-muted file:mr-2 file:rounded file:border-0 file:bg-surface-muted file:px-2 file:py-1 file:text-xs" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        <button type="submit" disabled={saving || !name.trim()} className="btn-primary text-sm">{saving ? "添加中…" : "添加"}</button>
      </form>
      {deliverables.length === 0 && <p className="text-sm text-ink-faint">暂无交付物</p>}
      {deliverables.map((d) => (
        <DeliverableRow
          key={d.id}
          deliverable={d}
          uploading={uploadingId === d.id}
          actionLoading={actionId === d.id}
          onDelete={async () => { await api.deleteDeliverable(d.id); await loadDeliverables(); }}
          onAttach={(selected) => void handleAttachFile(d.id, selected)}
          onSubmit={async () => { setActionId(d.id); try { await api.submitDeliverable(d.id); await loadDeliverables(); } finally { setActionId(null); } }}
          onAccept={async () => { setActionId(d.id); try { await api.acceptDeliverable(d.id); await loadDeliverables(); } finally { setActionId(null); } }}
          onReject={async () => { if (!window.confirm("确定驳回该交付物？")) return; setActionId(d.id); try { await api.rejectDeliverable(d.id); await loadDeliverables(); } finally { setActionId(null); } }}
        />
      ))}
    </div>
  );
}

function DeliverableRow({ deliverable, uploading, onDelete, onAttach, onSubmit, onAccept, onReject, actionLoading }: {
  deliverable: BizDeliverable;
  uploading: boolean;
  onDelete: () => void;
  onAttach: (file: File | null) => void;
  onSubmit: () => void;
  onAccept: () => void;
  onReject: () => void;
  actionLoading: boolean;
}) {
  const [filename, setFilename] = useState<string | null>(null);

  useEffect(() => {
    if (!deliverable.attachment_id) {
      setFilename(null);
      return;
    }
    let cancelled = false;
    void api.getAttachment(deliverable.attachment_id).then((att) => {
      if (!cancelled) setFilename(att.filename);
    }).catch(() => {
      if (!cancelled) setFilename(deliverable.attachment_id ?? null);
    });
    return () => { cancelled = true; };
  }, [deliverable.attachment_id]);

  return (
    <div className="card flex flex-wrap items-center justify-between gap-3 p-4">
      <div>
        <p className="font-medium text-ink">
          {deliverable.name}
          {deliverable.version ? <span className="ml-2 text-xs text-ink-faint">{deliverable.version}</span> : null}
        </p>
        <p className="text-xs text-ink-muted">
          {DELIV_TYPE_LABELS[deliverable.type] ?? deliverable.type} · {DELIV_STATUS_LABELS[deliverable.status] ?? deliverable.status}
          {filename ? <span className="ml-2 text-ink-faint">· 📎 {filename}</span> : null}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {(deliverable.status === "draft" || deliverable.status === "rejected") && (
          <button type="button" className="btn-sm-outline text-xs" disabled={actionLoading} onClick={onSubmit}>
            {actionLoading ? "处理中…" : "提交验收"}
          </button>
        )}
        {deliverable.status === "submitted" && (
          <>
            <button type="button" className="btn-primary text-xs" disabled={actionLoading} onClick={onAccept}>
              {actionLoading ? "处理中…" : "验收通过"}
            </button>
            <button type="button" className="btn-sm-outline text-xs text-red-600" disabled={actionLoading} onClick={onReject}>
              驳回
            </button>
          </>
        )}
        {!deliverable.attachment_id ? (
          <>
            <input type="file" className="max-w-[10rem] text-xs text-ink-muted file:mr-1 file:rounded file:border-0 file:bg-surface-muted file:px-2 file:py-1 file:text-xs" disabled={uploading} onChange={(e) => { onAttach(e.target.files?.[0] ?? null); e.target.value = ""; }} />
            {uploading ? <span className="text-xs text-ink-muted">上传中…</span> : null}
          </>
        ) : null}
        <button type="button" className="text-xs text-red-600 hover:underline" onClick={onDelete}>删除</button>
      </div>
    </div>
  );
}
