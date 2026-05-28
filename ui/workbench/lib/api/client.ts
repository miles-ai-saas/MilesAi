/**
 * HTTP 客户端与请求原语（供各域 api 模块复用）。
 */

import axios, { type AxiosInstance } from "axios";
import type { ApiResponse } from "../types";
import { getAccessToken, useAuthStore } from "../auth-store";
import { getApiErrorMessage } from "../api-error";
import type { PageResult } from "../types";
import { normalizePageResult } from "../pagination";

const baseURL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function createClient(): AxiosInstance {
  const client = axios.create({ baseURL, timeout: 120000 });
  client.interceptors.request.use((config) => {
    const token = getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });
  client.interceptors.response.use(
    (res) => res,
    (err) => {
      if (err.response?.status === 401 && typeof window !== "undefined") {
        const hadToken = !!getAccessToken();
        if (hadToken) {
          useAuthStore.getState().logout();
          window.location.href = "/login";
        }
      }
      return Promise.reject(new Error(getApiErrorMessage(err)));
    },
  );
  return client;
}

export const http = createClient();

export function unwrap<T>(body: ApiResponse<T>): T {
  if (body.code !== 0) {
    throw new Error(body.message || "请求失败");
  }
  return body.data as T;
}

export async function get<T>(url: string): Promise<T> {
  const res = await http.get<ApiResponse<T>>(url);
  return unwrap(res.data);
}

export async function getPage<T>(url: string): Promise<PageResult<T>> {
  const raw = await get<PageResult<T> | T[]>(url);
  return normalizePageResult<T>(raw);
}

export async function post<T>(url: string, data?: unknown): Promise<T> {
  const res = await http.post<ApiResponse<T>>(url, data);
  return unwrap(res.data);
}

function readTraceId(headers: Record<string, unknown>, body: ApiResponse<unknown>): string | undefined {
  const fromHeader = headers["x-trace-id"];
  if (typeof fromHeader === "string" && fromHeader.trim()) return fromHeader.trim();
  if (typeof body.trace_id === "string" && body.trace_id.trim()) return body.trace_id.trim();
  return undefined;
}

export async function postWithTrace<T extends object>(
  url: string,
  data?: unknown,
): Promise<T & { trace_id?: string }> {
  const res = await http.post<ApiResponse<T>>(url, data);
  const payload = unwrap(res.data);
  const trace_id = readTraceId(res.headers as Record<string, unknown>, res.data);
  return trace_id ? { ...payload, trace_id } : payload;
}

export async function put<T>(url: string, data?: unknown): Promise<T> {
  const res = await http.put<ApiResponse<T>>(url, data);
  return unwrap(res.data);
}

export async function patch<T>(url: string, data?: unknown): Promise<T> {
  const res = await http.patch<ApiResponse<T>>(url, data);
  return unwrap(res.data);
}
