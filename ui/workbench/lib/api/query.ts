/** 查询串辅助（tag_ids 等）。 */

export function appendTagIds(base: string, tagIds?: string[]): string {
  if (!tagIds?.length) return base;
  return tagIds.reduce((s, id) => `${s}&tag_ids=${encodeURIComponent(id)}`, base);
}
