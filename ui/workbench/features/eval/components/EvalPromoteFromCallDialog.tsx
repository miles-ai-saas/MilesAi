"use client";

import { useEffect, useState } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { api } from "@/lib/api";
import type { EvalCase, EvalDataset } from "@/lib/types";

type Props = {
  open: boolean;
  agentId: string;
  callId: string;
  defaultName?: string;
  onClose: () => void;
  onPromoted?: (created: EvalCase) => void | Promise<void>;
};

export function EvalPromoteFromCallDialog({
  open,
  agentId,
  callId,
  defaultName,
  onClose,
  onPromoted,
}: Props) {
  const [datasets, setDatasets] = useState<EvalDataset[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [name, setName] = useState("");
  const [preferSessionText, setPreferSessionText] = useState(true);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setError("");
    setName(defaultName?.slice(0, 128) ?? "");
    setPreferSessionText(true);
    setLoading(true);
    void api
      .listEvalDatasets(1, 100)
      .then((page) => {
        setDatasets(page.items);
        setDatasetId(page.items[0]?.id ?? "");
      })
      .catch((e) => setError(e instanceof Error ? e.message : "加载数据集失败"))
      .finally(() => setLoading(false));
  }, [open, defaultName]);

  const canSubmit = !!datasetId && !!agentId && !!callId;

  const submit = async () => {
    if (!canSubmit) return;
    setBusy(true);
    setError("");
    try {
      const created = await api.promoteEvalCaseFromCallRecord(datasetId, {
        agent_id: agentId,
        call_id: callId,
        name: name.trim() || null,
        prefer_session_text: preferSessionText,
      });
      await onPromoted?.(created);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "升格失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ResourceDialog
      open={open}
      title="升格为评测用例"
      description="成功或失败调用均可升格；有答案时默认 expected.contains=助手答案，并写入来源 call_id / call_status。"
      size="md"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" disabled={busy} onClick={onClose}>
            取消
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={busy || !canSubmit || loading}
            onClick={() => void submit()}
          >
            {busy ? "升格中…" : "升格"}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <label className="block space-y-1.5">
          <span className="text-sm font-medium text-ink">目标数据集</span>
          <select
            className="input-field w-full"
            value={datasetId}
            disabled={loading}
            onChange={(e) => setDatasetId(e.target.value)}
          >
            {loading ? <option value="">加载中…</option> : null}
            {!loading && datasets.length === 0 ? <option value="">暂无数据集，请先在评测页创建</option> : null}
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}（{d.case_count} 用例）
              </option>
            ))}
          </select>
        </label>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium text-ink">用例名称（可选）</span>
          <input
            className="input-field w-full"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="默认取用户问题前缀"
            maxLength={128}
          />
        </label>
        <label className="flex items-start gap-2 text-sm text-ink">
          <input
            type="checkbox"
            className="mt-0.5"
            checked={preferSessionText}
            onChange={(e) => setPreferSessionText(e.target.checked)}
          />
          <span>
            优先使用会话全文
            <span className="mt-0.5 block text-xs text-ink-muted">关闭则仅用调用记录 preview。</span>
          </span>
        </label>
        {error ? <p className="text-sm text-red-600">{error}</p> : null}
      </div>
    </ResourceDialog>
  );
}
