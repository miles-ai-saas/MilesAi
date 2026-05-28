/** 智能体内置生图/生视频工具的确认与等待文案。 */

export const GENERATIVE_TOOL_SLUGS = {
  image: "generate_image",
  video: "generate_video",
} as const;

const SIZE_RE = /^(\d+)\s*[xX×]\s*(\d+)$/;

function parseSize(size: string): { w: number; h: number } | null {
  const m = SIZE_RE.exec(size.trim());
  if (!m) return null;
  return { w: Number(m[1]), h: Number(m[2]) };
}

/** 与 backend integrations/generative/policy 对齐 */
export function needsHighResImageConfirm(params: Record<string, unknown> | undefined): boolean {
  if (!params) return false;
  const n = Number(params.n ?? 1);
  if (n >= 3) return true;
  const size = String(params.size ?? "1024x1024");
  const dims = parseSize(size);
  if (!dims) return false;
  return Math.max(dims.w, dims.h) >= 1280 || dims.w * dims.h > 1024 * 1024;
}

/** 待确认卡片下方的补充说明 */
export function generativeToolConfirmNote(slug: string | undefined | null, params?: Record<string, unknown>): string | null {
  if (slug === GENERATIVE_TOOL_SLUGS.video) {
    const res = String(params?.resolution ?? "").toUpperCase();
    const base = "生视频通常需 1–5 分钟，将按模型与时长计费；确认后开始调用，请勿关闭页面。";
    return res === "1080P" ? `${base}（当前为 1080P）` : base;
  }
  if (slug === GENERATIVE_TOOL_SLUGS.image) {
    if (needsHighResImageConfirm(params)) {
      return "当前为大尺寸或多张生图，将消耗更多额度；确认后执行。";
    }
    return "将调用生图模型生成图片；若带参考图则为图生图。";
  }
  return null;
}

export function generativeToolConfirmButtonLabel(slug: string | undefined | null): string {
  if (slug === GENERATIVE_TOOL_SLUGS.video) return "确认并生成视频";
  if (slug === GENERATIVE_TOOL_SLUGS.image) return "确认并生图";
  return "确认执行";
}

/** 已确认、请求进行中的状态文案 */
export function generativeToolBusyLabel(slug: string | undefined | null): string | null {
  if (slug === GENERATIVE_TOOL_SLUGS.video) {
    return "正在生成视频，通常需 1–5 分钟，请稍候…";
  }
  if (slug === GENERATIVE_TOOL_SLUGS.image) {
    return "正在生图，任务提交后将在后台执行，请稍候…";
  }
  return null;
}
