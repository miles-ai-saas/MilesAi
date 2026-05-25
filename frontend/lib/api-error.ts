import { isAxiosError } from "axios";
import type { ApiResponse } from "./types";

/** 从 axios / 业务异常中提取后端返回的 message。 */
export function getApiErrorMessage(err: unknown, fallback = "请求失败"): string {
  if (isAxiosError(err)) {
    const data = err.response?.data;
    if (data && typeof data === "object" && "message" in data) {
      const msg = (data as ApiResponse<unknown>).message;
      if (typeof msg === "string" && msg.trim()) return msg;
    }
    return err.message || fallback;
  }
  if (err instanceof Error && err.message.trim()) return err.message;
  return fallback;
}
