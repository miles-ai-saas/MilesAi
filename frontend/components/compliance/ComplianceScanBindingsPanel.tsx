"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { WordLibrary } from "@/lib/types";

type Props = {
  onSaved?: () => void;
};

export function ComplianceScanBindingsPanel({ onSaved }: Props) {
  const [libraries, setLibraries] = useState<WordLibrary[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getComplianceScanBindings();
      setLibraries(data.libraries);
      setSelected(new Set(data.library_ids));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const save = async () => {
    setSaving(true);
    setMsg("");
    try {
      await api.setComplianceScanBindings([...selected]);
      setMsg("已保存扫描配置");
      onSaved?.();
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <section className="col-span-full rounded-xl border border-line bg-surface-subtle/40 px-4 py-3 text-sm text-ink-muted">
        加载扫描配置…
      </section>
    );
  }

  const scanningOff = selected.size === 0;

  return (
    <section className="col-span-full rounded-xl border border-line bg-surface px-4 py-4 shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-ink">参与扫描的词库</h2>
          <p className="mt-0.5 text-xs text-ink-muted">
            未勾选任何词库时，对话与内容<strong>不会</strong>进行敏感词检测。
          </p>
        </div>
        <button type="button" className="btn-sm-primary shrink-0" disabled={saving} onClick={() => void save()}>
          {saving ? "保存中…" : "保存配置"}
        </button>
      </div>

      {scanningOff && (
        <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50/80 px-3 py-2 text-xs text-amber-900">
          当前未绑定词库，合规扫描已关闭。
        </p>
      )}

      <ul className="mt-3 flex flex-wrap gap-2">
        {libraries.map((lib) => {
          const checked = selected.has(lib.id);
          const disabled = !lib.is_active;
          return (
            <li key={lib.id}>
              <label
                className={`inline-flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-1.5 text-xs transition ${
                  checked
                    ? "border-brand/40 bg-brand-light text-brand"
                    : "border-line bg-surface-muted/50 text-ink-muted hover:border-line-soft"
                } ${disabled ? "opacity-50" : ""}`}
              >
                <input
                  type="checkbox"
                  className="rounded border-line text-brand focus:ring-brand/30"
                  checked={checked}
                  disabled={disabled}
                  onChange={() => toggle(lib.id)}
                />
                <span className="font-medium">{lib.name}</span>
                <span className="tabular-nums text-ink-faint">{lib.word_count} 词</span>
                {!lib.is_active && <span className="text-ink-faint">（库已停用）</span>}
              </label>
            </li>
          );
        })}
      </ul>

      {msg && <p className="mt-2 text-xs text-ink-muted">{msg}</p>}
    </section>
  );
}
