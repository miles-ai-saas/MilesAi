"use client";

import { useEffect, useState } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { api } from "@/lib/api";
import type { EvalDataset } from "@/lib/types";

type Props = {
  open: boolean;
  dataset?: EvalDataset | null;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
};

export function EvalDatasetDialog({ open, dataset, onClose, onSaved }: Props) {
  const isEdit = !!dataset;
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setError("");
    setName(dataset?.name ?? "");
    setDescription(dataset?.description ?? "");
  }, [open, dataset]);

  const canSave = name.trim().length > 0;

  const save = async () => {
    if (!canSave) return;
    setBusy(true);
    setError("");
    try {
      if (isEdit && dataset) {
        await api.updateEvalDataset(dataset.id, {
          name: name.trim(),
          description: description.trim() || null,
        });
      } else {
        await api.createEvalDataset(name.trim(), description.trim() || undefined);
      }
      await onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ResourceDialog
      open={open}
      title={isEdit ? "编辑数据集" : "新建数据集"}
      description="评测数据集用于组织用例，供运行时批量调用智能体。"
      size="md"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" disabled={busy} onClick={onClose}>
            取消
          </button>
          <button type="button" className="btn-primary" disabled={busy || !canSave} onClick={() => void save()}>
            {busy ? "保存中…" : "保存"}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <label className="block space-y-1.5">
          <span className="text-sm font-medium text-ink">名称</span>
          <input
            className="input-field w-full"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="例如：客服 FAQ 基线"
            maxLength={128}
          />
        </label>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium text-ink">描述</span>
          <textarea
            className="input-field min-h-[96px] w-full resize-y"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="可选说明"
          />
        </label>
        {error ? <p className="text-sm text-red-600">{error}</p> : null}
      </div>
    </ResourceDialog>
  );
}
