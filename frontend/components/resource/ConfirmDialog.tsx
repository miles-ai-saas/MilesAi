"use client";

/** 轻量确认弹窗；状态机由 `useConfirmAction` 驱动（链路 §3）。 */

import type { ReactNode } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";

type Props = {
  open: boolean;
  title: string;
  description?: string;
  message?: ReactNode;
  children?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  loading?: boolean;
  onClose: () => void;
  onConfirm: () => void;
};

export function ConfirmDialog({
  open,
  title,
  description,
  message,
  children,
  confirmLabel = "确认",
  cancelLabel = "取消",
  destructive = false,
  loading = false,
  onClose,
  onConfirm,
}: Props) {
  const body = children ?? (message ? <p className="text-sm text-ink">{message}</p> : null);

  return (
    <ResourceDialog
      open={open}
      title={title}
      description={description}
      onClose={() => {
        if (!loading) onClose();
      }}
      footer={
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost" disabled={loading} onClick={onClose}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={
              destructive
                ? "rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
                : "btn-primary"
            }
            disabled={loading}
            onClick={onConfirm}
          >
            {loading ? "处理中…" : confirmLabel}
          </button>
        </div>
      }
    >
      {body}
    </ResourceDialog>
  );
}
