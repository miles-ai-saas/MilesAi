"use client";

/** 智能体名称内联重命名（PATCH /agents/{id} name）。 */

import { useEffect, useId, useRef, useState } from "react";
import { api } from "@/lib/api";

type Props = {
  agentId: string;
  name: string;
  onRenamed: (name: string) => void;
  /** 卡片标题等醒目样式 */
  prominent?: boolean;
  className?: string;
  disabled?: boolean;
};

export function AgentRenameInline({
  agentId,
  name,
  onRenamed,
  prominent = false,
  className = "",
  disabled = false,
}: Props) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!editing) setDraft(name);
  }, [name, editing]);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const cancel = () => {
    setDraft(name);
    setEditing(false);
  };

  const save = async () => {
    const trimmed = draft.trim();
    if (!trimmed) return;
    if (trimmed === name) {
      setEditing(false);
      return;
    }
    setBusy(true);
    try {
      const updated = await api.updateAgent(agentId, { name: trimmed });
      onRenamed(updated.name);
      setEditing(false);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "重命名失败";
      window.alert(msg);
    } finally {
      setBusy(false);
    }
  };

  if (editing) {
    return (
      <div
        className={`flex min-w-0 flex-1 items-center gap-1 ${className}`}
        onClick={(e) => e.stopPropagation()}
      >
        <label htmlFor={inputId} className="sr-only">
          智能体名称
        </label>
        <input
          id={inputId}
          ref={inputRef}
          className="input-field min-w-0 flex-1 py-1 text-sm"
          value={draft}
          maxLength={128}
          disabled={busy}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void save();
            if (e.key === "Escape") cancel();
          }}
        />
        <button
          type="button"
          className="btn-sm-primary shrink-0 px-2 py-1 text-xs"
          disabled={busy || !draft.trim()}
          onClick={() => void save()}
        >
          保存
        </button>
        <button
          type="button"
          className="btn-sm-ghost shrink-0 px-2 py-1 text-xs"
          disabled={busy}
          onClick={cancel}
        >
          取消
        </button>
      </div>
    );
  }

  return (
    <div className={`group flex min-w-0 max-w-full items-center gap-1 ${className}`}>
      <span
        className={`min-w-0 truncate ${prominent ? "font-medium text-ink" : "text-ink"}`}
        title={name}
      >
        {name}
      </span>
      {!disabled ? (
        <button
          type="button"
          className="btn-sm-ghost shrink-0 px-1 py-0 text-[10px] text-ink-faint opacity-70 hover:text-brand group-hover:opacity-100"
          aria-label="重命名智能体"
          title="重命名"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setEditing(true);
          }}
        >
          重命名
        </button>
      ) : null}
    </div>
  );
}
