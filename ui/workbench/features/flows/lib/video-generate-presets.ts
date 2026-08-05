/** VideoGenerate 检查器参数配方（仅 duration / resolution，不改模型与附件）。 */

export type VideoGenerateParamPreset = {
  id: string;
  label: string;
  duration: number;
  resolution: "720P" | "1080P";
};

export const VIDEO_GENERATE_PARAM_PRESETS: VideoGenerateParamPreset[] = [
  { id: "short_720", label: "短片 5s·720P", duration: 5, resolution: "720P" },
  { id: "medium_720", label: "稍长 10s·720P", duration: 10, resolution: "720P" },
  { id: "short_1080", label: "高清 5s·1080P", duration: 5, resolution: "1080P" },
];

export function matchVideoGeneratePreset(duration: unknown, resolution: unknown): string {
  const d = Number(duration ?? 5);
  const r = String(resolution ?? "720P");
  const hit = VIDEO_GENERATE_PARAM_PRESETS.find((p) => p.duration === d && p.resolution === r);
  return hit?.id ?? "";
}
