export const MEDIA_ASSETS_PAGE_DESC = "智能体与流程产生的图片/视频；可预览、管理，图片可升格写入知识库（不自动入库）。";

export function formatMediaBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}
