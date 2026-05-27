import type { AdminModelCatalog } from "@/lib/api";

export const VENDORS = [
  { value: "deepseek", label: "深度求索" },
  { value: "doubao", label: "豆包" },
  { value: "qwen", label: "通义千问" },
] as const;

export const MODEL_TYPES = [
  { value: "llm", label: "大语言模型" },
  { value: "reasoning", label: "推理模型" },
  { value: "vision", label: "图像理解" },
  { value: "embedding", label: "向量化" },
  { value: "rerank", label: "重排序" },
  { value: "image_gen", label: "图像生成" },
  { value: "video_gen", label: "视频生成" },
  { value: "asr", label: "语音识别" },
  { value: "tts", label: "语音合成" },
  { value: "other", label: "其它" },
] as const;

export const VENDOR_LABEL: Record<string, string> = Object.fromEntries(
  VENDORS.map((v) => [v.value, v.label]),
);

export const TYPE_LABEL: Record<string, string> = Object.fromEntries(
  MODEL_TYPES.map((t) => [t.value, t.label]),
);

export const STATUS_LABEL: Record<string, string> = {
  draft: "草稿",
  published: "已发布",
  deprecated: "已下架",
};

export const DEFAULT_API_BASE: Record<string, string> = {
  deepseek: "https://api.deepseek.com/v1",
  doubao: "https://ark.cn-beijing.volces.com/api/v3",
  qwen: "https://dashscope.aliyuncs.com/compatible-mode/v1",
};

export type ModelCatalogFormValues = {
  name: string;
  vendor: string;
  model_name: string;
  model_code: string;
  model_type: string;
  description: string;
  context_window: string;
  api_base: string;
  api_key: string;
  clear_api_key: boolean;
  badge: string;
  sort_order: number;
  is_featured: boolean;
  is_active: boolean;
};

export function emptyForm(vendor = "deepseek"): ModelCatalogFormValues {
  return {
    name: "",
    vendor,
    model_name: "",
    model_code: "",
    model_type: "llm",
    description: "",
    context_window: "",
    api_base: DEFAULT_API_BASE[vendor] ?? "",
    api_key: "",
    clear_api_key: false,
    badge: "",
    sort_order: 0,
    is_featured: false,
    is_active: true,
  };
}

export function fromRow(m: AdminModelCatalog): ModelCatalogFormValues {
  return {
    name: m.name,
    vendor: m.vendor,
    model_name: m.model_name,
    model_code: m.model_code ?? "",
    model_type: m.model_type,
    description: m.description ?? "",
    context_window: m.context_window ?? "",
    api_base: m.api_base ?? DEFAULT_API_BASE[m.vendor] ?? "",
    api_key: "",
    clear_api_key: false,
    badge: m.badge ?? "",
    sort_order: m.sort_order,
    is_featured: m.is_featured,
    is_active: m.is_active,
  };
}

export function toPayload(v: ModelCatalogFormValues, isCreate: boolean) {
  const body: Record<string, unknown> = {
    name: v.name.trim(),
    vendor: v.vendor,
    model_name: v.model_name.trim(),
    model_type: v.model_type,
    description: v.description.trim() || null,
    context_window: v.context_window.trim() || null,
    api_base: v.api_base.trim() || null,
    badge: v.badge.trim() || null,
    sort_order: v.sort_order,
    is_featured: v.is_featured,
    is_active: v.is_active,
  };
  if (isCreate) {
    body.model_code = v.model_code.trim();
    if (v.api_key.trim()) body.api_key = v.api_key.trim();
  } else {
    if (v.api_key.trim()) body.api_key = v.api_key.trim();
    if (v.clear_api_key) body.clear_api_key = true;
  }
  return body;
}

export function statusBadgeClass(status: string) {
  if (status === "published") return "status-badge-published";
  if (status === "deprecated") return "status-badge-deprecated";
  return "status-badge-draft";
}
