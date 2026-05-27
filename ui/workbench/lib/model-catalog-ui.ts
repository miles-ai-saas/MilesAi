/**
 * 模型目录 UI：厂商/类型标签优先 `GET /models/meta`（`ModelCatalogMeta`），
 * 未加载时用下方常量 fallback。链路见 `lib/chains.ts、enum-meta.ts`。
 */

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

/** 卡片下方说明文案 */
export function credentialHint(m: ModelConfig): string {
  if (m.source === "custom") {
    if (m.credential_status === "tenant") return "已配置 API Key，可直接绑定使用";
    return "请在编辑时填写 API Key 后方可调用";
  }
  if (m.credential_status === "platform") return "平台已配置密钥，可直接绑定使用";
  if (m.credential_status === "tenant") return "当前使用租户自有 Key（优先于平台密钥）";
  return "平台尚未为该模型配置密钥，请联系管理员；若您自有 Key，可选用下方「使用自有 Key」";
}

/** 自定义模型缺 Key 时展示 */
export function isCustomMissingKey(m: ModelConfig): boolean {
  return m.source === "custom" && m.credential_status === "missing";
}

/** 内置模型平台未配 Key */
export function isBuiltinPlatformMissing(m: ModelConfig): boolean {
  return m.source === "builtin" && m.credential_status === "missing";
}

export function isBuiltinReady(m: ModelConfig): boolean {
  return m.source === "builtin" && m.credential_status === "platform";
}

export function isBuiltinByok(m: ModelConfig): boolean {
  return m.source === "builtin" && m.credential_status === "tenant";
}
