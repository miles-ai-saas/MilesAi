/** 模型目录展示文案与凭证状态。 */

import type { ModelCatalogMeta, ModelConfig } from "@/lib/types";

const MODEL_TYPE_LABELS: Record<string, string> = {
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

/** 对话类模型类型（与后端 integrations.litellm.adapter.CHAT_MODEL_TYPES 对齐） */
export const CHAT_MODEL_TYPES = new Set<string>(["llm", "reasoning", "vision"]);

const SOURCE_LABELS: Record<string, string> = {
  builtin: "内置模型",
  custom: "自定义模型",
};

const CREDENTIAL_STATUS_LABELS: Record<string, string> = {
  platform: "平台密钥可用",
  tenant: "租户自有 Key",
  missing: "未配置密钥",
};

export function modelVendorLabel(vendor: string, meta?: ModelCatalogMeta | null): string {
  return meta?.vendors.find((v) => v.value === vendor)?.label ?? vendor;
}

export function modelTypeLabel(t: string, meta?: ModelCatalogMeta | null): string {
  return meta?.model_types.find((x) => x.value === t)?.label ?? MODEL_TYPE_LABELS[t] ?? t;
}

export function modelSourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source;
}

export function modelCredentialStatusLabel(status: string): string {
  return CREDENTIAL_STATUS_LABELS[status] ?? status;
}

export function modelCredentialHint(m: ModelConfig): string {
  if (m.source === "custom") {
    if (m.credential_status === "tenant") return "已配置 API Key，可直接绑定使用";
    return "请在编辑时填写 API Key 后方可调用";
  }
  if (m.credential_status === "platform") return "平台已配置密钥，可直接绑定使用";
  if (m.credential_status === "tenant") return "当前使用租户自有 Key（优先于平台密钥）";
  return "平台尚未为该模型配置密钥，请联系管理员；若您自有 Key，可配置 BYOK";
}

export function isCustomMissingKey(m: ModelConfig): boolean {
  return m.source === "custom" && m.credential_status === "missing";
}

export function isBuiltinPlatformMissing(m: ModelConfig): boolean {
  return m.source === "builtin" && m.credential_status === "missing";
}

export function isBuiltinReady(m: ModelConfig): boolean {
  return m.source === "builtin" && m.credential_status === "platform";
}

export function isBuiltinByok(m: ModelConfig): boolean {
  return m.source === "builtin" && m.credential_status === "tenant";
}
