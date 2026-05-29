/** 流程画布含生图/生视频节点时的调试运行提示。 */

import type { FlowGraph } from "@/lib/types";

export type FlowGenerativeRunHint = {
  hasImageGenerate: boolean;
  hasVideoGenerate: boolean;
  /** 运行前展示的说明；无生成节点时为 null */
  preRunMessage: string | null;
  /** busy 时运行按钮文案 */
  busyRunLabel: string;
};

export function analyzeFlowGenerativeRun(graph: FlowGraph): FlowGenerativeRunHint {
  const types = new Set((graph.nodes ?? []).map((n) => n.type));
  const hasImageGenerate = types.has("ImageGenerate");
  const hasVideoGenerate = types.has("VideoGenerate");

  if (!hasImageGenerate && !hasVideoGenerate) {
    return {
      hasImageGenerate: false,
      hasVideoGenerate: false,
      preRunMessage: null,
      busyRunLabel: "运行中…",
    };
  }

  const parts: string[] = [];
  if (hasVideoGenerate) {
    parts.push("含生视频节点：同步等待可能需数分钟，请勿关闭页面");
  }
  if (hasImageGenerate) {
    parts.push("含生图节点：将调用 image_gen 模型");
  }

  let busyRunLabel = "运行中…";
  if (hasVideoGenerate) busyRunLabel = "生视频中…";
  else if (hasImageGenerate) busyRunLabel = "生图中…";

  return {
    hasImageGenerate,
    hasVideoGenerate,
    preRunMessage: parts.join("；"),
    busyRunLabel,
  };
}
