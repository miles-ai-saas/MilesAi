export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T | null;
}

export type { PageResult } from "@milesai/ui-shared/lib/pagination";
