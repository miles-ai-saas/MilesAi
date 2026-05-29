"use client";

/**
 * 画布节点卡片 UI（链路 §6）；Handle 见 flow-node-schemas.ts。
 * ImageGenerate / VideoGenerate 摘要见节点 data.model_config_id、duration 等。
 */
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { NODE_PALETTE } from "@/features/flows/lib/flow-nodes";
import { getNodeHandles, sourceHandleClass, targetHandleClass } from "@/features/flows/lib/flow-node-schemas";

const TARGET_TOP_OFFSET: Record<string, string> = {
  query: "20%",
  hits: "50%",
  prompt: "25%",
  input: "50%",
  image_attachment_id: "65%",
  last_frame_attachment_id: "85%",
};

export function FlowNodeCard({ type, data, selected }: NodeProps) {
  const meta = NODE_PALETTE.find((p) => p.type === type);
  const label = (data?.label as string) || meta?.label || String(type);
  const color = meta?.color || "#64748b";
  const nodeType = String(type);
  const { targets, sources } = getNodeHandles(nodeType);
  const isCondition = nodeType === "ConditionBranch";
  const isGrade = nodeType === "RelevanceGrade";
  const isImageGen = nodeType === "ImageGenerate";
  const isVideoGen = nodeType === "VideoGenerate";
  const d = data as Record<string, unknown>;
  const GRADE_LABELS: Record<string, string> = {
    good: "好",
    poor: "低",
    none: "无",
  };

  return (
    <div
      className={`relative min-w-[160px] rounded-lg border-2 bg-surface px-3 py-2 shadow-sm ${selected ? "border-brand ring-2 ring-brand/20" : "border-line"}`}
    >
      {targets.map((hid) => (
        <Handle
          key={`t-${hid}`}
          type="target"
          position={targets.length > 1 ? Position.Top : Position.Left}
          id={hid}
          style={targets.length > 1 ? { left: TARGET_TOP_OFFSET[hid] ?? "50%" } : undefined}
          className={targetHandleClass(hid)}
        />
      ))}

      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full" style={{ background: color }} />
        <span className="text-sm font-medium text-ink">{label}</span>
      </div>
      <p className="mt-1 text-xs text-ink-muted">{nodeType}</p>
      {nodeType === "PlatformTool" && (
        <p className="mt-1 truncate text-[10px] text-sky-700">{String((data as Record<string, unknown>)?.tool_slug ?? "未配置 tool_slug")}</p>
      )}
      {nodeType === "SubFlow" && (
        <p className="mt-1 truncate text-[10px] text-indigo-700">{String((data as Record<string, unknown>)?.label ?? "未选子流程")}</p>
      )}
      {nodeType === "PromptTemplate" && Boolean(d.prompt_template_id) && <p className="mt-1 truncate text-[10px] text-violet-700">模板库引用</p>}
      {isCondition && <p className="mt-1 text-[10px] text-pink-600">模式: {String((data as Record<string, unknown>)?.mode ?? "has_hits")}</p>}
      {isGrade && <p className="mt-1 text-[10px] text-violet-600">阈值: {String(d.relevance_threshold ?? 0.35)}</p>}
      {isImageGen && (
        <p className="mt-1 text-[10px] text-rose-700">
          {d.model_config_id ? "image_gen 已配置" : "未选 image_gen 模型"}
          {d.size ? ` · ${String(d.size)}` : ""}
          {d.image_attachment_id ? " · 图生图" : ""}
        </p>
      )}
      {isVideoGen && (
        <p className="mt-1 text-[10px] text-violet-700">
          {d.model_config_id ? "video_gen 已配置" : "未选 video_gen 模型"}
          {` · ${String(d.duration ?? 5)}s · ${String(d.resolution ?? "720P")}`}
          {d.image_attachment_id && d.last_frame_attachment_id ? " · 首尾帧" : d.image_attachment_id ? " · 首帧" : ""}
        </p>
      )}

      {sources.map((hid, idx) => (
        <Handle
          key={`s-${hid}`}
          type="source"
          position={Position.Right}
          id={hid}
          style={sources.length > 1 ? { top: `${32 + idx * 30}%` } : undefined}
          className={sourceHandleClass(hid)}
        />
      ))}
      {isCondition && (
        <>
          <span className="absolute -right-7 top-[28%] text-[9px] text-emerald-600">是</span>
          <span className="absolute -right-7 top-[58%] text-[9px] text-rose-600">否</span>
        </>
      )}
      {isGrade &&
        sources.map((hid, idx) => (
          <span key={`lbl-${hid}`} className="absolute -right-7 text-[9px] text-ink-muted" style={{ top: `${22 + idx * 28}%` }}>
            {GRADE_LABELS[hid] ?? hid}
          </span>
        ))}
    </div>
  );
}

export const flowNodeTypes = Object.fromEntries(NODE_PALETTE.map((p) => [p.type, FlowNodeCard]));
