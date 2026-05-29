/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";

export type { EnumOption };

export type { PageResult } from "@milesai/ui-shared/lib/pagination";

export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T | null;
  trace_id?: string;
}
