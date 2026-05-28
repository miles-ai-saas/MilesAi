import { isAxiosError } from "axios";
type ErrorBody = {
  message?: unknown;
  detail?: unknown;
  code?: unknown;
};

function stripValidationPrefix(msg: string): string {
  const prefixes = ["Value error, ", "Assertion failed, "];
  for (const p of prefixes) {
    if (msg.startsWith(p)) return msg.slice(p.length);
  }
  return msg;
}

function messageFromDetail(detail: unknown): string | null {
  if (typeof detail === "string" && detail.trim()) {
    return stripValidationPrefix(detail.trim());
  }
  if (Array.isArray(detail)) {
    const first = detail[0];
    if (first && typeof first === "object") {
      const row = first as { msg?: unknown; loc?: unknown };
      const msg = typeof row.msg === "string" && row.msg.trim() ? stripValidationPrefix(row.msg.trim()) : "";
      if (!msg) return null;
      const loc = Array.isArray(row.loc) ? row.loc.filter((x) => x !== "body" && x !== "query" && x !== "path").join(".") : "";
      return loc ? `${loc}: ${msg}` : msg;
    }
  }
  return null;
}

function messageFromResponseData(data: unknown): string | null {
  if (!data) return null;
  if (typeof data === "string" && data.trim()) return data.trim();
  if (typeof data !== "object") return null;

  const body = data as ErrorBody;
  if (typeof body.message === "string" && body.message.trim()) {
    return stripValidationPrefix(body.message.trim());
  }
  return messageFromDetail(body.detail);
}

function networkFallback(err: { message?: string; code?: string }): string | null {
  const msg = err.message?.trim() ?? "";
  if (msg === "Network Error" || err.code === "ERR_NETWORK") {
    return "无法连接 API 服务，请确认后端已启动且 NEXT_PUBLIC_ADMIN_API_URL 配置正确";
  }
  if (err.code === "ECONNABORTED" || msg.toLowerCase().includes("timeout")) {
    return "请求超时，请稍后重试";
  }
  return null;
}

/** 从 axios / 业务异常中提取后端返回的 message。 */
export function getApiErrorMessage(err: unknown, fallback = "请求失败"): string {
  if (isAxiosError(err)) {
    const fromBody = messageFromResponseData(err.response?.data);
    if (fromBody) return fromBody;

    const net = networkFallback(err);
    if (net) return net;

    if (err.response?.status) {
      return `请求失败（HTTP ${err.response.status}）`;
    }
    return err.message?.trim() || fallback;
  }
  if (err instanceof Error && err.message.trim()) {
    const net = networkFallback(err);
    if (net) return net;
    return stripValidationPrefix(err.message.trim());
  }
  return fallback;
}
