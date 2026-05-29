"use client";

import { Background, Controls, MiniMap, ReactFlow, useReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { forwardRef, useCallback } from "react";
import { FlowNodeInspector } from "@/features/flows/components/FlowNodeInspector";
import { flowNodeTypes } from "@/features/flows/components/FlowNodeCard";
import type { FlowCanvasHandle, FlowCanvasProps } from "@/features/flows/components/flow-canvas-types";
import { useFlowCanvasCore } from "@/features/flows/hooks/use-flow-canvas-core";
import { PALETTE_GROUPS, paletteItemsByGroup, type NodeType } from "@/features/flows/lib/flow-nodes";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import type { FlowTemplate } from "@/lib/types";

function FlowCanvasToolbar({
  onPushHistory,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  insertableTemplates,
  onInsertTemplate,
}: {
  onPushHistory: () => void;
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  insertableTemplates: FlowTemplate[];
  onInsertTemplate: (template: FlowTemplate) => void;
}) {
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

function FlowCanvasPalette({
  open,
  onToggle,
  onDropPalette,
}: {
  open: boolean;
  onToggle: (open: boolean) => void;
  onDropPalette: (type: NodeType) => void;
}) {
  if (open) {
    return (
      <aside className="flex w-44 shrink-0 flex-col border-r border-line bg-surface sm:w-48">
        <div className="flex items-center justify-between border-b border-line px-2 py-2">
          <span className="text-xs font-semibold text-ink-muted">节点</span>
          <button type="button" className="btn-sm-ghost !px-1.5 text-[10px]" onClick={() => onToggle(false)} title="收起节点面板">
            ‹
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          <div className="flex flex-col gap-3">
            {PALETTE_GROUPS.map((group) => {
              const items = paletteItemsByGroup(group.key);
              if (!items.length) return null;
              return (
                <div key={group.key}>
                  <p className="mb-1 px-1 text-[10px] font-semibold uppercase tracking-wide text-ink-faint">{group.label}</p>
                  <div className="flex flex-col gap-1">
                    {items.map((item) => (
                      <button
                        key={item.type}
                        type="button"
                        onClick={() => onDropPalette(item.type)}
                        className="flex items-center gap-2 rounded-lg border border-line bg-surface px-2 py-2 text-left text-xs transition hover:border-brand/50 hover:bg-brand-light"
                      >
                        <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: item.color }} />
                        <span className="text-ink">{item.label}</span>
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
          <p className="mt-3 text-[10px] leading-relaxed text-ink-faint">选中节点在右侧编辑；Delete 删除；Ctrl+Z 撤销</p>
        </div>
      </aside>
    );
  }

  return (
    <div className="flex w-9 shrink-0 flex-col items-center border-r border-line bg-surface py-2">
      <button
        type="button"
        className="btn-sm-ghost !px-1 text-lg leading-none"
        onClick={() => onToggle(true)}
        title="展开节点面板"
        aria-label="展开节点面板"
      >
        ›
      </button>
    </div>
  );
}

export const FlowCanvasInner = forwardRef<FlowCanvasHandle, FlowCanvasProps>(function FlowCanvasInner(
  { initialGraph, onGraphChange, currentFlowId, kbs = [], models = [], prompts = [], toolCatalog = [], className, canvasRef },
  ref,
) {
  const canvas = useFlowCanvasCore({
    initialGraph,
    onGraphChange,
    canvasRef,
    forwardedRef: ref,
  });

  return (
    <div className={`flex h-full min-h-0 flex-col ${className ?? ""}`}>
      <FlowCanvasToolbar
        onPushHistory={canvas.pushHistory}
        canUndo={canvas.canUndo}
        canRedo={canvas.canRedo}
        onUndo={canvas.undo}
        onRedo={canvas.redo}
        insertableTemplates={canvas.insertableTemplates}
        onInsertTemplate={canvas.insertTemplate}
      />
      {canvas.connectHint && <p className="border-b border-amber-200/80 bg-amber-50 px-3 py-1.5 text-xs text-amber-900">{canvas.connectHint}</p>}
      <div className="flex min-h-0 flex-1">
        <FlowCanvasPalette open={canvas.paletteOpen} onToggle={canvas.setPaletteOpen} onDropPalette={canvas.onDropPalette} />
        <div className="min-w-0 flex-1 bg-white">
          <ReactFlow
            nodes={canvas.nodes}
            edges={canvas.edges}
            onNodesChange={canvas.handleNodesChange}
            onEdgesChange={canvas.handleEdgesChange}
            onConnect={canvas.onConnect}
            onNodeDragStart={canvas.onNodeDragStart}
            onSelectionChange={canvas.onSelectionChange}
            nodesDraggable
            nodesConnectable
            elementsSelectable
            nodeTypes={flowNodeTypes}
            deleteKeyCode={["Backspace", "Delete"]}
            multiSelectionKeyCode={["Shift", "Meta", "Control"]}
            selectionOnDrag
            fitView
            proOptions={{ hideAttribution: true }}
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </div>
        <FlowNodeInspector
          node={canvas.selectedNode}
          kbs={kbs}
          models={models}
          prompts={prompts}
          toolCatalog={toolCatalog}
          currentFlowId={currentFlowId}
          onChange={canvas.updateNodeData}
        />
      </div>
      {canvas.confirmDialog}
    </div>
  );
});
