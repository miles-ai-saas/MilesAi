/**
 * 附件展示文案：优先 GET /attachments/meta，未加载时用本地 fallback。
 * 页面用 optionLabel(meta?.xxx, value)；约定见 docs/guides/hooks.md §9。
 */

import { optionLabel, type EnumOption } from "@/lib/enum-meta";
import type { AttachmentMeta } from "@/lib/types";

const PURPOSE_FALLBACK: EnumOption[] = [
  { value: "general", label: "通用" },
  { value: "chat", label: "对话" },
  { value: "agent", label: "智能体" },
  { value: "flow", label: "流程" },
];

const FILTER_FALLBACK: EnumOption[] = [{ value: "", label: "全部用途" }, ...PURPOSE_FALLBACK];

export function attachmentPurposeLabel(purpose: string, meta?: AttachmentMeta | null): string {
  return optionLabel(meta?.purposes, purpose) || optionLabel(PURPOSE_FALLBACK, purpose) || purpose;
}

export function attachmentPurposeFilterOptions(meta?: AttachmentMeta | null): EnumOption[] {
  return meta?.purpose_filters?.length ? meta.purpose_filters : FILTER_FALLBACK;
}

export function attachmentPurposeUploadOptions(meta?: AttachmentMeta | null): EnumOption[] {
  return meta?.purposes?.length ? meta.purposes : PURPOSE_FALLBACK;
}
