import type { ModelCatalogMeta, ModelConfig } from "@/lib/types";

export const MODEL_TYPE_LABELS: Record<string, string> = {
  llm: "大语言模型",
  reasoning: "推理模型",
  vision: "图像理解",
  embedding: "向量化",
  rerank: "重排序",
  image_gen: "图像生成",
  video_gen: "视频生成",
  asr: "语音识别",
  tts: "语音合成",
  other: "其它",
};

export const SOURCE_LABELS: Record<string, string> = {
  builtin: "内置模型",
  custom: "自定义模型",
};

export function vendorLabel(vendor: string, meta?: ModelCatalogMeta | null): string {
  return meta?.vendors.find((v) => v.value === vendor)?.label ?? vendor;
}

export function modelTypeLabel(t: string, meta?: ModelCatalogMeta | null): string {
  return meta?.model_types.find((x) => x.value === t)?.label ?? MODEL_TYPE_LABELS[t] ?? t;
}

export function credentialHint(m: ModelConfig): string {
  if (m.credential_status === "platform") return "平台已配置密钥";
  if (m.credential_status === "tenant") return "已配置租户密钥";
  return "需配置 API Key";
}
