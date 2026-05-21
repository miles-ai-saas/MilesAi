export function filterBySearch<T>(
  items: T[],
  search: string,
  getSearchText: (item: T) => string,
): T[] {
  const q = search.trim().toLowerCase();
  if (!q) return items;
  return items.filter((item) => getSearchText(item).toLowerCase().includes(q));
}
