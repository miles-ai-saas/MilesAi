/**
 * 分页契约（链路 §3）：`buildPageQuery` 拼 query → `getPage` → `normalizePageResult`。
 * 见 `lib/chains.ts` §3。
 */

export {
  DEFAULT_PAGE_SIZE,
  PAGE_SIZE_OPTIONS,
  buildPageQuery,
  needsPagination,
  normalizePageResult,
  totalPages,
} from "@milesai/ui-shared/lib/pagination";

export type { PageResult } from "@milesai/ui-shared/lib/pagination";
