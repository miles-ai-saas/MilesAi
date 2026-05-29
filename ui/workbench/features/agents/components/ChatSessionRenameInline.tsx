"use client";

/** 会话标题内联重命名（本地 chat-sessions）。 */

import { useEffect, useId, useRef, useState } from "react";
import { MAX_SESSION_TITLE_LENGTH } from "@/features/agents/lib/chat-sessions";

type Props = {
  title: string;
  onRename: (title: string) => void;
  prominent?: boolean;
  className?: string;
  disabled?: boolean;
};

export function ChatSessionRenameInline({ title, onRename, prominent = false, className = "", disabled = false }: Props) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(title);

  useEffect(() => {
    if (!editing) setDraft(title);
  }, [title, editing]);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const cancel = () => {
    setDraft(title);
    setEditing(false);
  };

  const save = () => {
    const trimmed = draft.trim();
    if (!trimmed) return;
    if (trimmed === title) {
      setEditing(false);
      return;
    }
    onRename(trimmed);
    setEditing(false);
  };

  if (editing) {
    return (
      <div className={`flex min-w-0 flex-1 items-center gap-1 ${className}`} onClick={(e) => e.stopPropagation()}>
        <label htmlFor={inputId} className="sr-only">
          会话名称
        </label>
        <input
          id={inputId}
          ref={inputRef}
          className="input-field min-w-0 flex-1 py-1 text-sm"
          value={draft}
          maxLength={MAX_SESSION_TITLE_LENGTH}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") save();
            if (e.key === "Escape") cancel();
          }}
        />
        <button type="button" className="btn-sm-primary shrink-0 px-2 py-1 text-xs" onClick={save}>
          保存
        </button>
        <button type="button" className="btn-sm-ghost shrink-0 px-2 py-1 text-xs" onClick={cancel}>
          取消
        </button>
      </div>
    );
  }

  return (
    <div className={`group flex min-w-0 max-w-full items-center gap-1 ${className}`}>
      <span className={`min-w-0 truncate ${prominent ? "font-semibold text-ink" : "font-medium text-ink"}`} title={title}>
        {title}
      </span>
      {!disabled ? (
        <button
          type="button"
          className="btn-sm-ghost shrink-0 px-1 py-0 text-[10px] text-ink-faint opacity-70 hover:text-brand group-hover:opacity-100"
          aria-label="重命名会话"
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
