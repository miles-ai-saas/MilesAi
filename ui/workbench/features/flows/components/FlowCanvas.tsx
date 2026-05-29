"use client";

/**
 * 流程画布（链路 §6）：ReactFlow ↔ flow-nodes；FlowNodeInspector / flow-node-schemas。
 */
import { ReactFlowProvider } from "@xyflow/react";
import { forwardRef } from "react";
import { FlowCanvasInner } from "@/features/flows/components/FlowCanvasInner";
import type { FlowCanvasHandle, FlowCanvasProps } from "@/features/flows/components/flow-canvas-types";

export type { FlowCanvasHandle, FlowCanvasProps } from "@/features/flows/components/flow-canvas-types";

export const FlowCanvas = forwardRef<FlowCanvasHandle, FlowCanvasProps>(function FlowCanvas(props, ref) {
  return (
    <ReactFlowProvider>
      <FlowCanvasInner {...props} ref={ref} />
    </ReactFlowProvider>
  );
});

export default FlowCanvas;
