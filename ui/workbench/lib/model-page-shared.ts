/** 模型页共享常量。 */

export const MODELS_PAGE_DESC =
  "内置模型由平台统一提供密钥，可直接选用；自定义 OpenAI 兼容接入需自行配置 API Key。";

export const VENDOR_ORDER = ["deepseek", "doubao", "qwen"] as const;

export type SourceFilter = "" | "builtin" | "custom";
