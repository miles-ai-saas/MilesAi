/**
 * 后端各域 GET …/meta 返回的枚举选项（与 app.common.schemas.enum_meta.EnumOption 一致）。
 * 各域 `*-labels.ts` 在 meta 未加载时用本地 fallback，加载后以后端文案为准。
 */

export type EnumOption = {
  /** 与 API/ORM 存库值一致 */
  value: string;
  /** 列表、下拉、徽章展示文案 */
  label: string;
  hint?: string | null;
  /** 钩子：是否已接线实现 */
  implemented?: boolean | null;
};

/** 按 value 取 label；未命中时回退为 value 本身 */
export function optionLabel(options: EnumOption[] | undefined, value: string): string {
  return options?.find((o) => o.value === value)?.label ?? value;
}

/** 按 value 取 hint（表单说明、卡片副标题等） */
export function optionHint(options: EnumOption[] | undefined, value: string): string | undefined {
  const h = options?.find((o) => o.value === value)?.hint;
  return h ?? undefined;
}
