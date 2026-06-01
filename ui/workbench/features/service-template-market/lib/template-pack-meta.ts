/** 服务线 → 默认场景分类（与后端 template_pack_meta 一致） */

export const SERVICE_LINE_DEFAULT_CATEGORY: Record<string, string> = {
  brand_identity: "brand",
  video_production: "video",
  exhibition: "exhibition",
  event: "event",
  training: "training",
  signage: "signage",
  cultural_product: "cultural",
  print: "print",
};

export function defaultCategoryForServiceLine(serviceLine: string): string {
  return SERVICE_LINE_DEFAULT_CATEGORY[serviceLine] ?? "general";
}
