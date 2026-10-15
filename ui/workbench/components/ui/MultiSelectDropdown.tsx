"use client";

/** 表单内通用下拉多选：触发器摘要 + 面板勾选，可选下方已选标签。 */

import { useEffect, useId, useRef, useState } from "react";

export type MultiSelectOption = {
  value: string;
  label: string;
  detail?: string;
};

type Props = {
  options: MultiSelectOption[];
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  emptyText?: string;
  disabled?: boolean;
  /** 面板标题 */
  panelTitle?: string;
  /** 触发器下方展示已选项，便于一眼确认 */
  showSelectedTags?: boolean;
  className?: string;
};

export function MultiSelectDropdown({
  options,
  value,
  onChange,
  placeholder = "请选择",
  emptyText = "暂无可选项",
  disabled,
  panelTitle = "可多选",
  showSelectedTags = true,
  className,
}: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const listId = useId();

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const selected = options.filter((o) => value.includes(o.value));
  const triggerLabel =
    selected.length === 0
      ? placeholder
      : selected.length === 1
        ? selected[0].label
        : `已选 ${selected.length} 项`;

  const toggle = (id: string) => {
    if (value.includes(id)) onChange(value.filter((x) => x !== id));
    else onChange([...value, id]);
  };

  const remove = (id: string) => onChange(value.filter((x) => x !== id));

  if (options.length === 0) {
    return <p className="text-xs text-ink-faint">{emptyText}</p>;
  }

  return (
    <div ref={rootRef} className={`relative ${className ?? ""}`}>
      <button
        type="button"
        disabled={disabled}
        className="input-field flex w-full items-center justify-between gap-2 text-left text-sm disabled:cursor-not-allowed disabled:opacity-50"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls={listId}
        onClick={() => setOpen((o) => !o)}
      >
        <span className={selected.length === 0 ? "truncate text-ink-faint" : "truncate text-ink"}>{triggerLabel}</span>
        <span className="shrink-0 text-[10px] text-ink-faint" aria-hidden>
          {open ? "▲" : "▼"}
        </span>
      </button>

      {open ? (
        <div
          id={listId}
          className="absolute left-0 right-0 z-50 mt-1 rounded-lg border border-line bg-surface py-1 shadow-panel"
          role="listbox"
          aria-multiselectable
          aria-label={panelTitle}
        >
          <div className="flex items-center justify-between border-b border-line-soft px-3 py-2">
            <span className="text-xs font-medium text-ink-muted">{panelTitle}</span>
            {value.length > 0 ? (
              <button type="button" className="text-xs text-brand hover:underline" onClick={() => onChange([])}>
                清除
              </button>
            ) : null}
          </div>
          <ul className="max-h-56 overflow-y-auto py-1">
            {options.map((o) => {
              const checked = value.includes(o.value);
              return (
                <li key={o.value} role="option" aria-selected={checked}>
                  <label className="flex cursor-pointer items-start gap-2 px-3 py-1.5 text-sm hover:bg-surface-muted">
                    <input
                      type="checkbox"
                      className="mt-0.5 rounded border-line text-brand"
                      checked={checked}
                      onChange={() => toggle(o.value)}
                    />
                    <span className="min-w-0">
                      <span className="block text-ink">{o.label}</span>
                      {o.detail ? <span className="block text-[11px] text-ink-faint">{o.detail}</span> : null}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      {showSelectedTags && selected.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {selected.map((o) => (
            <span
              key={o.value}
              className="inline-flex max-w-full items-center gap-1 rounded-md border border-line-soft bg-surface-muted px-2 py-0.5 text-xs text-ink"
            >
              <span className="truncate">{o.label}</span>
              {!disabled ? (
                <button
                  type="button"
                  className="shrink-0 text-ink-faint hover:text-brand"
                  aria-label={`移除 ${o.label}`}
                  onClick={() => remove(o.value)}
                >
                  ×
                </button>
              ) : null}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
