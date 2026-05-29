"use client";

import { Background, Controls, MiniMap, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { forwardRef } from "react";
import { FlowCanvasPalette } from "@/features/flows/components/FlowCanvasPalette";
import { FlowCanvasToolbar } from "@/features/flows/components/FlowCanvasToolbar";
import { FlowNodeInspector } from "@/features/flows/components/FlowNodeInspector";
import { flowNodeTypes } from "@/features/flows/components/FlowNodeCard";
import type { FlowCanvasHandle, FlowCanvasProps } from "@/features/flows/components/flow-canvas-types";
import { useFlowCanvasCore } from "@/features/flows/hooks/use-flow-canvas-core";

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
