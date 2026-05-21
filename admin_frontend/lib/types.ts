export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T | null;
}

export interface PageResult<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}
