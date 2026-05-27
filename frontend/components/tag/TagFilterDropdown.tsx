"use client";

/** 列表页标签多选下拉筛选（顶栏紧凑场景，替代原芯片式筛选）。 */

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { TenantTag } from "@/lib/types";

type Props = {
  value: string[];
  onChange: (ids: string[]) => void;
};

export function TagFilterDropdown({ value, onChange }: Props) {
  const [tags, setTags] = useState<TenantTag[]>([]);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void api.listTags().then(setTags).catch(() => setTags([]));
  }, []);

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

  if (tags.length === 0) return null;

  const selected = tags.filter((t) => value.includes(t.id));
  const triggerLabel =
    selected.length === 0
      ? "全部标签"
      : selected.length === 1
        ? selected[0].name
        : `已选 ${selected.length} 个标签`;

  const toggle = (id: string) => {
    if (value.includes(id)) onChange(value.filter((x) => x !== id));
    else onChange([...value, id]);
  };

  return (
    <div ref={rootRef} className="relative shrink-0">
      <button
        type="button"
        className="input-field flex w-auto min-w-[7.5rem] max-w-[11rem] items-center justify-between gap-2 text-sm"
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={() => setOpen((o) => !o)}
      >
        <span className="truncate">{triggerLabel}</span>
        <span className="shrink-0 text-[10px] text-ink-faint" aria-hidden>
          ▼
        </span>
      </button>
      {open ? (
        <div
          className="absolute right-0 z-50 mt-1 min-w-[12rem] rounded-lg border border-line bg-surface py-1 shadow-panel"
          role="listbox"
          aria-multiselectable
          aria-label="筛选标签"
        >
          <div className="flex items-center justify-between border-b border-line-soft px-3 py-2">
            <span className="text-xs font-medium text-ink-muted">筛选标签（可多选）</span>
            {value.length > 0 ? (
              <button
                type="button"
                className="text-xs text-brand hover:underline"
                onClick={() => onChange([])}
              >
                清除
              </button>
            ) : null}
          </div>
          <ul className="max-h-56 overflow-y-auto py-1">
            {tags.map((t) => {
              const checked = value.includes(t.id);
              return (
                <li key={t.id} role="option" aria-selected={checked}>
                  <label className="flex cursor-pointer items-center gap-2 px-3 py-1.5 text-sm hover:bg-surface-muted">
                    <input
                      type="checkbox"
                      className="rounded border-line text-brand"
                      checked={checked}
                      onChange={() => toggle(t.id)}
                    />
                    <span className="text-ink">{t.name}</span>
                  </label>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
