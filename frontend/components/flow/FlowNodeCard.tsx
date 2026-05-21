"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { NODE_PALETTE } from "@/lib/flow-nodes";

export function FlowNodeCard({ type, data, selected }: NodeProps) {
  const meta = NODE_PALETTE.find((p) => p.type === type);
  const label = (data?.label as string) || meta?.label || String(type);
  const color = meta?.color || "#64748b";

  return (
    <div
      className={`min-w-[160px] rounded-lg border-2 bg-white px-3 py-2 shadow-sm ${
        selected ? "border-brand ring-2 ring-brand/20" : "border-slate-200"
      }`}
    >
      <Handle type="target" position={Position.Left} id="input" className="!bg-slate-400" />
      <Handle type="target" position={Position.Top} id="query" className="!bg-blue-400" />
      <Handle type="target" position={Position.Top} id="hits" style={{ left: "70%" }} className="!bg-green-400" />
      <Handle type="target" position={Position.Top} id="prompt" style={{ left: "85%" }} className="!bg-violet-400" />
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full" style={{ background: color }} />
        <span className="text-sm font-medium text-slate-800">{label}</span>
      </div>
      <p className="mt-1 text-xs text-slate-500">{String(type)}</p>
      <Handle type="source" position={Position.Right} id="output" className="!bg-slate-600" />
    </div>
  );
}

export const flowNodeTypes = Object.fromEntries(
  NODE_PALETTE.map((p) => [p.type, FlowNodeCard])
);
