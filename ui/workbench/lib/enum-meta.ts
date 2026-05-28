/**
 * 全站枚举展示契约（与 backend `app/common/schemas/enum_meta.py` 一致）。
 *
 * 必要链路（文案单一来源，避免前后端枚举漂移）：
 *   1. `backend/app/tenant/<module>/meta.py` — 维护 value/label/hint
 *   2. `GET /<module>/meta` — 须在 `/{id}` 等路径参数路由之前注册
 *   3. `lib/api.ts` — `get*Meta()`
 *   4. `lib/enum-meta-cache.tsx` + `hooks/use-enum-meta.ts` + `hooks/use-*-meta.ts` — AppShell 内按 cacheKey 缓存 meta
 *   5. `lib/*-labels.ts` 或 `document-status.ts` — `optionLabel(meta?.field, value)` + 本地 fallback
 *   6. 页面/组件 — 将 `meta` 传入 label 函数或 `statusOptions` 等 props
 *
 * 纯 UI Tab（如「全部」「广场/安装」）可保留在前端，不必进 meta。
 * 模块对照表见 `docs/guides/hooks.md` §9；全站链路索引见 `lib/chains.ts` §4。
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
