"use client";

/** 词条编辑（链路 §13）。 */
import { useEffect, useState } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { api } from "@/lib/api";
import { sensitiveActionLabel } from "@/lib/compliance-labels";
import type { EnumOption, LibraryWord } from "@/lib/types";

type Mode = "create" | "view" | "edit";

type Props = {
  open: boolean;
  mode: Mode;
  libraryId: string;
  word?: LibraryWord | null;
  sensitiveActions?: EnumOption[];
  onClose: () => void;
  onSaved: () => void | Promise<void>;
  onRequestEdit?: () => void;
};

export function LibraryWordDialog({
  open,
  mode,
  libraryId,
  word,
  onClose,
  onSaved,
  onRequestEdit,
  sensitiveActions = [],
}: Props) {
  const isView = mode === "view";
  const isCreate = mode === "create";

  const [text, setText] = useState("");
  const [action, setAction] = useState<"warn" | "block">("block");
  const [isActive, setIsActive] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setError("");
    if (word && !isCreate) {
      setText(word.word);
      setAction(word.action);
      setIsActive(word.is_active);
    } else {
      setText("");
      setAction("block");
      setIsActive(true);
    }
  }, [open, word, isCreate]);

  const save = async () => {
    if (isView) return;
    setBusy(true);
    setError("");
    try {
      if (isCreate) {
        if (!text.trim()) return;
        await api.addLibraryWord(libraryId, {
          word: text.trim(),
          action,
          is_active: isActive,
        });
      } else if (word) {
        await api.updateLibraryWord(libraryId, word.id, { action, is_active: isActive });
      }
      await onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  };

  const title = isCreate ? "添加词条" : isView ? "查看词条" : "编辑词条";

  return (
    <ResourceDialog
      open={open}
      title={title}
      description={
        isView
          ? "同一词面可加入多个词库；在本库内的处置方式可单独配置。"
          : undefined
      }
      size="md"
      onClose={onClose}
      footer={
        isView ? (
          <>
            <button type="button" className="btn-ghost" onClick={onClose}>
              关闭
            </button>
            {onRequestEdit && (
              <button type="button" className="btn-primary" onClick={onRequestEdit}>
                编辑
              </button>
            )}
          </>
        ) : (
          <>
            <button type="button" className="btn-ghost" disabled={busy} onClick={onClose}>
              取消
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={busy || (isCreate && !text.trim())}
              onClick={() => void save()}
            >
              {busy ? "保存中…" : "确定"}
            </button>
          </>
        )
      }
    >
      <div className="space-y-4">
        {isView ? (
          <>
            <div className="text-sm">
              <p className="text-xs text-ink-muted">敏感词</p>
              <p className="mt-1 font-medium text-ink">{word?.word}</p>
            </div>
            <div className="text-sm">
              <p className="text-xs text-ink-muted">处置方式</p>
              <p className="mt-1 text-ink">
                {sensitiveActionLabel(word?.action ?? "", null, sensitiveActions)}
                {word?.action === "block" ? "（拒绝请求）" : "（记录日志）"}
              </p>
            </div>
            <div className="text-sm">
              <p className="text-xs text-ink-muted">状态</p>
              <p className="mt-1 text-ink">{word?.is_active ? "已启用" : "已停用"}</p>
            </div>
          </>
        ) : (
          <>
            <label className="block space-y-1 text-sm">
              <span className="text-xs text-ink-muted">敏感词</span>
              <input
                className="input-field w-full"
                value={text}
                readOnly={!isCreate}
                disabled={!isCreate}
                onChange={(e) => setText(e.target.value)}
                placeholder="例如：违禁品"
              />
            </label>
            {!isCreate && (
              <p className="text-xs text-ink-faint">词面创建后不可修改；需更名请删除后重新添加。</p>
            )}
            <label className="block space-y-1 text-sm">
              <span className="text-xs text-ink-muted">处置方式</span>
              <select
                className="input-field w-full"
                value={action}
                onChange={(e) => setAction(e.target.value as "warn" | "block")}
              >
                {(sensitiveActions.length
                  ? sensitiveActions
                  : [
                      { value: "warn", label: "警告" },
                      { value: "block", label: "拦截" },
                    ]
                ).map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                    {o.hint ? ` — ${o.hint}` : ""}
                  </option>
                ))}
              </select>
            </label>
            {!isCreate && (
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                  className="rounded border-line text-brand"
                />
                <span>在本库中启用</span>
              </label>
            )}
          </>
        )}
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>
    </ResourceDialog>
  );
}
