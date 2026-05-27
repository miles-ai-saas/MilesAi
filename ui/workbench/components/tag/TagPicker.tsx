"use client";

/** 资源表单内标签选择（链路 §3）。 */
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { TenantTag } from "@/lib/types";

type Props = {
  value: string[];
  onChange: (ids: string[]) => void;
  disabled?: boolean;
};

export function TagPicker({ value, onChange, disabled }: Props) {
  const [allTags, setAllTags] = useState<TenantTag[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    try {
      setAllTags(await api.listTags());
    } catch {
      setAllTags([]);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const selected = allTags.filter((t) => value.includes(t.id));
  const available = allTags.filter((t) => !value.includes(t.id));

  const addExisting = (id: string) => {
    if (!value.includes(id)) onChange([...value, id]);
  };

  const remove = (id: string) => onChange(value.filter((x) => x !== id));

  const createAndAdd = async () => {
    const name = draft.trim();
    if (!name) return;
    setBusy(true);
    try {
      const tag = await api.createTag(name);
      setDraft("");
      await reload();
      addExisting(tag.id);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex min-h-[2rem] flex-wrap gap-1.5">
        {selected.map((t) => (
          <span
            key={t.id}
            className="inline-flex items-center gap-1 rounded-full bg-brand-light px-2.5 py-0.5 text-xs text-brand"
          >
            {t.name}
            {!disabled ? (
              <button
                type="button"
                className="hover:text-brand-dark"
                aria-label={`移除标签 ${t.name}`}
                onClick={() => remove(t.id)}
              >
                ×
              </button>
            ) : null}
          </span>
        ))}
        {selected.length === 0 ? (
          <span className="text-xs text-ink-muted">暂无标签</span>
        ) : null}
      </div>
      {!disabled ? (
        <div className="flex flex-wrap gap-2">
          <input
            className="input-field min-w-[8rem] flex-1 text-sm"
            placeholder="输入新标签名，回车创建"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void createAndAdd();
              }
            }}
          />
          <button
            type="button"
            className="btn-ghost border border-line text-xs"
            disabled={busy || !draft.trim()}
            onClick={() => void createAndAdd()}
          >
            添加标签
          </button>
        </div>
      ) : null}
      {!disabled && available.length > 0 ? (
        <div className="flex flex-wrap gap-1">
          {available.map((t) => (
            <button
              key={t.id}
              type="button"
              className="rounded-full border border-line px-2 py-0.5 text-xs text-ink-muted hover:border-brand hover:text-brand"
              onClick={() => addExisting(t.id)}
            >
              + {t.name}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
