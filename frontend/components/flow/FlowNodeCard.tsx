"use client";

/** 画布节点卡片 UI（链路 §6）。 */
/**
 * React Flow 节点卡片：Handle id 须与导出 graph_json 的 sourceHandle/targetHandle 一致。
 * 见 lib/flow-nodes.ts 与 backend flow_runtime/templates/README.md（RAG 模板边示例）。
 */
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { NODE_PALETTE } from "@/lib/flow-nodes";

export function FlowNodeCard({ type, data, selected }: NodeProps) {
  const meta = NODE_PALETTE.find((p) => p.type === type);
  const label = (data?.label as string) || meta?.label || String(type);
  const color = meta?.color || "#64748b";
  const isCondition = type === "ConditionBranch";

  return (
    <div
      className={`relative min-w-[160px] rounded-lg border-2 bg-white px-3 py-2 shadow-sm ${
        selected ? "border-brand ring-2 ring-brand/20" : "border-slate-200"
      }`}
    >
      <Handle type="target" position={Position.Left} id="input" className="!bg-slate-400" />
      <Handle type="target" position={Position.Top} id="query" className="!bg-blue-400" />
      <Handle
        type="target"
        position={Position.Top}
        id="hits"
        style={{ left: "70%" }}
        className="!bg-green-400"
      />
      <Handle
        type="target"
        position={Position.Top}
        id="prompt"
        style={{ left: "85%" }}
        className="!bg-violet-400"
      />
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full" style={{ background: color }} />
        <span className="text-sm font-medium text-slate-800">{label}</span>
      </div>
      <p className="mt-1 text-xs text-slate-500">{String(type)}</p>
      {type === "PlatformTool" && (
        <p className="mt-1 truncate text-[10px] text-sky-700">
          {String((data as Record<string, unknown>)?.tool_slug ?? "未配置 tool_slug")}
        </p>
      )}
      {isCondition && (
        <p className="mt-1 text-[10px] text-pink-600">
          模式: {String((data as Record<string, unknown>)?.mode ?? "has_hits")}
        </p>
      )}
      {isCondition ? (
        <>
          <Handle
            type="source"
            position={Position.Right}
            id="true"
            style={{ top: "38%" }}
            className="!bg-emerald-500"
          />
          <Handle
            type="source"
            position={Position.Right}
            id="false"
            style={{ top: "68%" }}
            className="!bg-rose-500"
          />
          <span className="absolute -right-7 top-[32%] text-[9px] text-emerald-600">是</span>
          <span className="absolute -right-7 top-[62%] text-[9px] text-rose-600">否</span>
        </>
      ) : (
        <Handle type="source" position={Position.Right} id="output" className="!bg-slate-600" />
      )}
    </div>
  );
}

export const flowNodeTypes = Object.fromEntries(
  NODE_PALETTE.map((p) => [p.type, FlowNodeCard]),
);
