"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { TenantTag } from "@/lib/types";

type Props = {
  value: string[];
  onChange: (ids: string[]) => void;
};

export function TagFilterSelect({ value, onChange }: Props) {
  const [tags, setTags] = useState<TenantTag[]>([]);

  useEffect(() => {
    void api.listTags().then(setTags).catch(() => setTags([]));
  }, []);

  if (tags.length === 0) return null;

  const toggle = (id: string) => {
    if (value.includes(id)) onChange(value.filter((x) => x !== id));
    else onChange([...value, id]);
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-xs text-ink-muted">标签</span>
      {tags.map((t) => {
        const active = value.includes(t.id);
        return (
          <button
            key={t.id}
            type="button"
            onClick={() => toggle(t.id)}
            className={`rounded-full border px-2 py-0.5 text-xs ${
              active
                ? "border-brand bg-brand-light text-brand"
                : "border-line text-ink-muted hover:border-brand"
            }`}
          >
            {t.name}
          </button>
        );
      })}
      {value.length > 0 ? (
        <button type="button" className="text-xs text-ink-muted hover:underline" onClick={() => onChange([])}>
          清除
        </button>
      ) : null}
    </div>
  );
}
