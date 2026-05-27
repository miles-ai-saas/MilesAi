"use client";

/** 轻量输入弹窗（链路 §3，如市场评分）。 */
import { useEffect, useState } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";

type Props = {
  open: boolean;
  title: string;
  description?: string;
  label?: string;
  placeholder?: string;
  defaultValue?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  loading?: boolean;
  onClose: () => void;
  onConfirm: (value: string) => void;
};

export function PromptDialog({
  open,
  title,
  description,
  label,
  placeholder,
  defaultValue = "",
  confirmLabel = "确认",
  cancelLabel = "取消",
  destructive = false,
  loading = false,
  onClose,
  onConfirm,
}: Props) {
  const [value, setValue] = useState(defaultValue);

  useEffect(() => {
    if (open) setValue(defaultValue);
  }, [open, defaultValue]);

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
            onClick={() => onConfirm(value)}
          >
            {loading ? "处理中…" : confirmLabel}
          </button>
        </div>
      }
    >
      <label className="block text-sm text-ink">
        {label && <span className="mb-1 block text-xs text-ink-muted">{label}</span>}
        <input
          className="input-field w-full"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={placeholder}
          autoFocus
        />
      </label>
    </ResourceDialog>
  );
}
