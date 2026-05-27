"use client";

/** 标签管理弹窗（链路 §3，`api` 标签 CRUD）。 */
import { useCallback, useEffect, useState } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { api } from "@/lib/api";
import type { TenantTag } from "@/lib/types";

type Props = {
  open: boolean;
  onClose: () => void;
};

export function TagManageDialog({ open, onClose }: Props) {
  const [items, setItems] = useState<TenantTag[]>([]);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    try {
      setItems(await api.listTags());
    } catch (e) {
      setItems([]);
      setMsg(e instanceof Error ? e.message : "加载失败");
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    setMsg("");
    void load();
  }, [open, load]);

  const onCreate = async () => {
    if (!name.trim()) return;
    setBusy(true);
    setMsg("");
    try {
      await api.createTag(name.trim());
      setName("");
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "创建失败");
    } finally {
      setBusy(false);
    }
  };

  const onDelete = async (row: TenantTag) => {
    if (!confirm(`确定删除标签「${row.name}」？将从所有资源上移除。`)) return;
    setBusy(true);
    try {
      await api.deleteTag(row.id);
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "删除失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ResourceDialog open={open} title="管理标签" size="md" onClose={onClose}>
      <p className="text-xs text-ink-muted">标签在租户内全局共用，可打在智能体、提示词、技能包、工具上。</p>
      <div className="mt-4 space-y-4">
        <div className="flex gap-2">
          <input
            className="input-field flex-1"
            placeholder="新标签名称"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void onCreate()}
          />
          <button type="button" className="btn-primary shrink-0" disabled={busy} onClick={() => void onCreate()}>
            添加
          </button>
        </div>
        {msg ? <p className="text-sm text-red-600">{msg}</p> : null}
        <ul className="divide-y divide-line rounded-lg border border-line">
          {items.length === 0 ? (
            <li className="px-3 py-4 text-center text-xs text-ink-muted">暂无标签</li>
          ) : null}
          {items.map((t) => (
            <li key={t.id} className="flex items-center justify-between gap-2 px-3 py-2 text-sm">
              <span>{t.name}</span>
              <button
                type="button"
                className="text-xs text-red-600 hover:underline"
                disabled={busy}
                onClick={() => void onDelete(t)}
              >
                删除
              </button>
            </li>
          ))}
        </ul>
      </div>
    </ResourceDialog>
  );
}
