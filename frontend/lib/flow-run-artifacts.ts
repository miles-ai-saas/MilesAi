/** 从流程运行 steps 提取生图/生视频附件，供调试面板预览。 */

export type FlowRunArtifact = {
  attachmentId: string;
  kind: "image" | "video";
  mimeType?: string | null;
  nodeId?: string;
  nodeType?: string;
  label?: string;
};

type StepRecord = Record<string, unknown>;

function pushArtifact(
  out: FlowRunArtifact[],
  seen: Set<string>,
  item: FlowRunArtifact,
) {
  const key = `${item.kind}:${item.attachmentId}`;
  if (seen.has(key)) return;
  seen.add(key);
  out.push(item);
}

function artifactFromDict(
  raw: Record<string, unknown>,
  meta: { nodeId?: string; nodeType?: string },
): FlowRunArtifact | null {
  const id = raw.attachment_id;
  const kind = raw.kind;
  if (typeof id !== "string" || (kind !== "image" && kind !== "video")) {
    return null;
  }
  const nodeType = meta.nodeType;
  const nodeId = meta.nodeId;
  const label =
    nodeType && nodeId
      ? `${nodeType} · ${nodeId.length > 8 ? `${nodeId.slice(0, 8)}…` : nodeId}`
      : nodeType;
  return {
    attachmentId: id,
    kind,
    mimeType: typeof raw.mime_type === "string" ? raw.mime_type : null,
    nodeId,
    nodeType,
    label,
  };
}

/** 从 output_preview 回退解析（旧运行或未带 artifact 字段时）。 */
function parsePreviewArtifact(preview: string): FlowRunArtifact | null {
  const idMatch = preview.match(/['"]attachment_id['"]\s*:\s*['"]([^'"]+)['"]/);
  const kindMatch = preview.match(/['"]kind['"]\s*:\s*['"](image|video)['"]/);
  if (!idMatch || !kindMatch) return null;
  const mimeMatch = preview.match(/['"]mime_type['"]\s*:\s*['"]([^'"]+)['"]/);
  return {
    attachmentId: idMatch[1],
    kind: kindMatch[1] as "image" | "video",
    mimeType: mimeMatch?.[1] ?? null,
  };
}

export function extractFlowRunArtifacts(
  steps: StepRecord[] | undefined | null,
): FlowRunArtifact[] {
  if (!steps?.length) return [];

  const out: FlowRunArtifact[] = [];
  const seen = new Set<string>();

  for (const s of steps) {
    const nodeId = typeof s.node_id === "string" ? s.node_id : undefined;
    const nodeType = typeof s.node_type === "string" ? s.node_type : undefined;
    const meta = { nodeId, nodeType };

    const single = s.artifact;
    if (single && typeof single === "object") {
      const item = artifactFromDict(single as Record<string, unknown>, meta);
      if (item) pushArtifact(out, seen, item);
    }

    const many = s.artifacts;
    if (Array.isArray(many)) {
      for (const raw of many) {
        if (raw && typeof raw === "object") {
          const item = artifactFromDict(raw as Record<string, unknown>, meta);
          if (item) pushArtifact(out, seen, item);
        }
      }
    }

    if (!single && typeof s.output_preview === "string") {
      const fromPreview = parsePreviewArtifact(s.output_preview);
      if (fromPreview) {
        pushArtifact(out, seen, {
          ...fromPreview,
          ...meta,
          label:
            nodeType && nodeId
              ? `${nodeType} · ${nodeId.slice(0, 8)}…`
              : nodeType,
        });
      }
    }
  }

  return out;
}
