"use client";

import { useCallback } from "react";
import { useReactFlow } from "@xyflow/react";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import type { FlowTemplate } from "@/lib/types";

type Props = {
  onPushHistory: () => void;
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  insertableTemplates: FlowTemplate[];
  onInsertTemplate: (template: FlowTemplate) => void;
};

export function FlowCanvasToolbar({
  onPushHistory,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  insertableTemplates,
  onInsertTemplate,
}: Props) {
  const { getNodes, getEdges, setNodes, setEdges, deleteElements } = useReactFlow();
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const deleteSelected = useCallback(() => {
    const selectedNodes = getNodes().filter((n) => n.selected);
    const selectedEdges = getEdges().filter((e) => e.selected);
    if (selectedNodes.length === 0 && selectedEdges.length === 0) return;
    onPushHistory();
    deleteElements({
      nodes: selectedNodes.map((n) => ({ id: n.id })),
      edges: selectedEdges.map((e) => ({ id: e.id })),
    });
  }, [getNodes, getEdges, deleteElements, onPushHistory]);

  const clearAll = useCallback(() => {
    if (getNodes().length === 0) return;
    requestConfirm({
      title: "清空画布",
      message: "确定清空画布上所有节点和连线？",
      destructive: true,
      confirmLabel: "确认清空",
      onConfirm: () => {
        onPushHistory();
        setNodes([]);
        setEdges([]);
      },
    });
  }, [getNodes, setNodes, setEdges, onPushHistory, requestConfirm]);

  return (
    <>
      <div className="flex flex-wrap items-center gap-1 border-b border-line bg-surface px-2 py-1.5">
        <button type="button" title="撤销 (Ctrl+Z)" disabled={!canUndo} onClick={onUndo} className="btn-sm-ghost disabled:opacity-40">
          撤销
        </button>
        <button type="button" title="重做 (Ctrl+Shift+Z)" disabled={!canRedo} onClick={onRedo} className="btn-sm-ghost disabled:opacity-40">
          重做
        </button>
        <span className="mx-0.5 h-4 w-px bg-line" />
        <button type="button" title="删除选中 (Delete)" onClick={deleteSelected} className="btn-sm text-red-600 hover:bg-red-50">
          删除
        </button>
        <button type="button" onClick={clearAll} className="btn-sm-ghost">
          清空
        </button>
        <span className="mx-0.5 h-4 w-px bg-line" />
        {insertableTemplates.length > 0 && (
          <label className="inline-flex items-center gap-1.5 text-sm">
            <span className="text-ink-muted">插入模板</span>
            <select
              className="input-field max-w-[11rem] py-1 text-sm"
              defaultValue=""
              onChange={(e) => {
                const id = e.target.value;
                e.target.value = "";
                const tpl = insertableTemplates.find((t) => t.id === id);
                if (tpl) onInsertTemplate(tpl);
              }}
            >
              <option value="" disabled>
                选择…
              </option>
              {insertableTemplates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      {confirmDialog}
    </>
  );
}
