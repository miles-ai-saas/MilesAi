/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";

export type { EnumOption };

export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T | null;
  trace_id?: string;
}


export interface PageResult<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

