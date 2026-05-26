const KIND_LABELS: Record<string, string> = {
  image: "图片",
  video: "视频",
};

const SOURCE_LABELS: Record<string, string> = {
  agent_tool: "智能体生成",
  flow_node: "流程生成",
};

export function mediaAssetKindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind;
}

export function mediaAssetSourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source;
}
