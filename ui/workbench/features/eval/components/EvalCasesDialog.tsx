"use client";

import { useCallback, useEffect, useState } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { api } from "@/lib/api";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import {
  EXPECTED_MODE_OPTIONS,
  buildExpectedPayload,
  formatExpectedPreview,
  parseExpectedForm,
  type ExpectedMode,
} from "@/features/eval/lib/eval-labels";
import type { EvalCase, EvalDataset } from "@/lib/types";

type Props = {
  open: boolean;
  dataset: EvalDataset | null;
  onClose: () => void;
  onChanged?: () => void | Promise<void>;
};

type CaseForm = {
  name: string;
  query: string;
  expectedMode: ExpectedMode;
  expectedValue: string;
  /** 编辑时保留原 expected（含 _source） */
  previousExpected: Record<string, unknown> | null;
};

const emptyForm = (): CaseForm => ({
  name: "",
  query: "",
  expectedMode: "contains",
  expectedValue: "",
  previousExpected: null,
});

export function EvalCasesDialog({ open, dataset, onClose, onChanged }: Props) {
  const { requestConfirm, confirmDialog } = useConfirmAction();
  const [cases, setCases] = useState<EvalCase[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<CaseForm>(emptyForm);
  const [busy, setBusy] = useState(false);

  const loadCases = useCallback(async () => {
    if (!dataset) return;
    setLoading(true);
    setError("");
    try {
      const page = await api.listEvalCases(dataset.id, 1, 100);
      setCases(page.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载用例失败");
    } finally {
      setLoading(false);
    }
  }, [dataset]);

  useEffect(() => {
    if (!open || !dataset) return;
    setEditingId(null);
    setForm(emptyForm());
    void loadCases();
  }, [open, dataset, loadCases]);

  const startCreate = () => {
    setEditingId(null);
    setForm(emptyForm());
  };

  const startEdit = (c: EvalCase) => {
    const parsed = parseExpectedForm(c.expected);
    setEditingId(c.id);
    setForm({
      name: c.name ?? "",
      query: c.query,
      expectedMode: parsed.mode === "none" ? "contains" : parsed.mode,
      expectedValue: parsed.value,
      previousExpected: c.expected ?? null,
    });
  };

  const saveCase = async () => {
    if (!dataset || !form.query.trim()) return;
    if (form.expectedMode !== "none" && !form.expectedValue.trim()) {
      setError(form.expectedMode === "rubric" ? "请填写评分标准" : "请填写期望值");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const expected = buildExpectedPayload(
        form.expectedMode,
        form.expectedValue,
        form.previousExpected,
      );
      const payload = {
        query: form.query.trim(),
        name: form.name.trim() || undefined,
        expected,
      };
      if (editingId) {
        await api.updateEvalCase(dataset.id, editingId, {
          query: payload.query,
          name: payload.name ?? null,
          expected: payload.expected,
        });
      } else {
        await api.createEvalCase(dataset.id, payload);
      }
      setEditingId(null);
      setForm(emptyForm());
      await loadCases();
      await onChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  };

  const deleteCase = (c: EvalCase) => {
    if (!dataset) return;
    requestConfirm({
      title: "删除用例",
      message: (
        <>
          确定删除用例 <span className="font-medium">{c.name || c.query.slice(0, 32)}</span>？
        </>
      ),
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deleteEvalCase(dataset.id, c.id);
        await loadCases();
        await onChanged?.();
      },
    });
  };

  return (
    <>
      <ResourceDialog
        open={open}
        title={dataset ? `管理用例 · ${dataset.name}` : "管理用例"}
        description="期望支持精确匹配、包含子串或评分标准（rubric，配合运行侧 auto / LLM Judge）。"
        size="lg"
        onClose={onClose}
        footer={
          <button type="button" className="btn-ghost" onClick={onClose}>
            关闭
          </button>
        }
      >
        <div className="space-y-6">
          <section className="space-y-3 rounded-lg border border-line p-4">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-sm font-medium text-ink">{editingId ? "编辑用例" : "新建用例"}</h3>
              {editingId ? (
                <button type="button" className="btn-ghost text-xs" onClick={startCreate}>
                  改为新建
                </button>
              ) : null}
            </div>
            <label className="block space-y-1">
              <span className="text-xs text-ink-muted">名称（可选）</span>
              <input
                className="input-field w-full"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                maxLength={128}
              />
            </label>
            <label className="block space-y-1">
              <span className="text-xs text-ink-muted">查询</span>
              <textarea
                className="input-field min-h-[80px] w-full resize-y"
                value={form.query}
                onChange={(e) => setForm((f) => ({ ...f, query: e.target.value }))}
                placeholder="发送给智能体的用户问题"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-xs text-ink-muted">期望类型</span>
              <select
                className="input-field w-full"
                value={form.expectedMode}
                onChange={(e) =>
                  setForm((f) => ({ ...f, expectedMode: e.target.value as ExpectedMode }))
                }
              >
                {EXPECTED_MODE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
            {form.expectedMode === "rubric" ? (
              <label className="block space-y-1">
                <span className="text-xs text-ink-muted">评分标准</span>
                <textarea
                  className="input-field min-h-[96px] w-full resize-y"
                  value={form.expectedValue}
                  onChange={(e) => setForm((f) => ({ ...f, expectedValue: e.target.value }))}
                  placeholder="例如：回答应包含退款时效，语气礼貌，不得编造政策"
                />
                <span className="text-[11px] text-ink-faint">
                  运行请选「自动」或「LLM Judge」；纯「规则」模式不会调用 Judge。
                </span>
              </label>
            ) : (
              <label className="block space-y-1">
                <span className="text-xs text-ink-muted">期望值</span>
                <input
                  className="input-field w-full"
                  value={form.expectedValue}
                  disabled={form.expectedMode === "none"}
                  onChange={(e) => setForm((f) => ({ ...f, expectedValue: e.target.value }))}
                  placeholder={form.expectedMode === "exact" ? "完整答案" : "须包含的片段"}
                />
              </label>
            )}
            <div className="flex justify-end">
              <button
                type="button"
                className="btn-primary"
                disabled={busy || !form.query.trim()}
                onClick={() => void saveCase()}
              >
                {busy ? "保存中…" : editingId ? "更新用例" : "添加用例"}
              </button>
            </div>
          </section>

          <section className="space-y-2">
            <h3 className="text-sm font-medium text-ink">用例列表（{cases.length}）</h3>
            {loading ? <p className="text-sm text-ink-muted animate-pulse">加载中…</p> : null}
            {!loading && cases.length === 0 ? (
              <p className="text-sm text-ink-muted">暂无用例，请先添加。</p>
            ) : null}
            <ul className="divide-y divide-line rounded-lg border border-line">
              {cases.map((c) => (
                <li key={c.id} className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0 space-y-1">
                    <p className="text-sm font-medium text-ink">{c.name || "未命名用例"}</p>
                    <p className="text-xs text-ink-muted line-clamp-2">{c.query}</p>
                    <p className="text-[11px] text-ink-faint">{formatExpectedPreview(c.expected)}</p>
                  </div>
                  <div className="flex shrink-0 gap-3 text-xs">
                    <button type="button" className="text-brand hover:underline" onClick={() => startEdit(c)}>
                      编辑
                    </button>
                    <button type="button" className="text-red-600 hover:underline" onClick={() => deleteCase(c)}>
                      删除
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </section>

          {error ? <p className="text-sm text-red-600">{error}</p> : null}
        </div>
      </ResourceDialog>
      {confirmDialog}
    </>
  );
}
