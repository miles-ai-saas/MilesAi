"use client";

import type { KnowledgeBase } from "@/lib/types";

export function MediaAssetPromoteDialog({
  open,
  kbs,
  promoteKbId,
  busy,
  onKbChange,
  onClose,
  onConfirm,
}: {
  open: boolean;
  kbs: KnowledgeBase[];
  promoteKbId: string;
  busy: boolean;
  onKbChange: (id: string) => void;
  onClose: () => void;
  onConfirm: () => void;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-xl border border-line bg-surface p-5 shadow-lg">
        <h2 className="text-base font-semibold text-ink">加入知识库</h2>
        <p className="mt-1 text-sm text-ink-muted">将复制文件到所选知识库并触发解析（占用存储配额）。</p>
        <label className="mt-4 block text-xs font-medium text-ink-muted">
          目标知识库
          <select className="input-field mt-1 w-full text-sm" value={promoteKbId} onChange={(e) => onKbChange(e.target.value)}>
            {kbs.map((kb) => (
              <option key={kb.id} value={kb.id}>
                {kb.name}
              </option>
            ))}
          </select>
        </label>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="btn-secondary text-sm" disabled={busy} onClick={onClose}>
            取消
          </button>
          <button type="button" className="btn-primary text-sm" disabled={busy || !promoteKbId} onClick={onConfirm}>
            {busy ? "处理中…" : "确认"}
          </button>
        </div>
      </div>
    </div>
  );
}
