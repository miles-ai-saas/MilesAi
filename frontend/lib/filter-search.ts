/** 列表页客户端关键字过滤（在 `usePagedList` 结果上二次筛选，链路 §3）。 */

export function filterBySearch<T>(
  items: T[],
  search: string,
  getSearchText: (item: T) => string,
): T[] {
  const q = search.trim().toLowerCase();
  if (!q) return items;
  return items.filter((item) => getSearchText(item).toLowerCase().includes(q));
}
