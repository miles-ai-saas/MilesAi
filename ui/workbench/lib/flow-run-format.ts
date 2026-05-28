type FlowStep = Record<string, unknown>;

export type FlowCompileErrorDetail = {
  code: string;
  message: string;
  node_id?: string | null;
};

export function formatCompileErrors(errors: string[], details?: FlowCompileErrorDetail[]): string {
  if (details?.length) {
    return details.map((d) => (d.node_id ? `[${d.node_id}] ${d.message}` : d.message)).join("\n");
  }
  return errors.join("\n");
}

function stepOutputLine(s: FlowStep): string {
  const art = s.artifact;
  if (art && typeof art === "object") {
    const kind = (art as Record<string, unknown>).kind;
    const id = (art as Record<string, unknown>).attachment_id;
    if (kind === "image" || kind === "video") {
      const short = typeof id === "string" && id.length > 8 ? `${id.slice(0, 8)}…` : id;
      return `\n  → 已生成${kind === "video" ? "视频" : "图片"}（${short}，见上方预览）`;
    }
  }
  const childSteps = s.child_steps;
  if (Array.isArray(childSteps) && childSteps.length > 0) {
    const count = typeof s.child_step_count === "number" ? s.child_step_count : childSteps.length;
    return `\n  → 子流程 ${String(s.child_flow_id ?? "").slice(0, 8)}… · ${count} 步（摘要 ${childSteps.length} 条）`;
  }
  return s.output_preview ? `\n  ${s.output_preview}` : "";
}

export function formatFlowSteps(steps: FlowStep[]): string {
  return steps
    .map((s, i) => {
      const t = String(s.type ?? "step");
      const nid = s.node_id ? ` · ${s.node_id}` : "";
      const nt = s.node_type ? ` (${s.node_type})` : "";
      return `${i + 1}. [${t}]${nid}${nt}${stepOutputLine(s)}`;
    })
    .join("\n");
}
