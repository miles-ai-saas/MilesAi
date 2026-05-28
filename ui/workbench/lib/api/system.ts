import type {
  ConfigDefinition,
  RuntimeInfo,
  InfraStatus,
  InfraComponentStatus,
} from "../types";
import { get, post, put } from "./client";

export const systemApi = {
  listConfigDefinitions: () => get<ConfigDefinition[]>("/system/configs/definitions"),

  getRuntimeInfo: () => get<RuntimeInfo>("/system/configs/runtime"),

  getTenantObjectStorage: () =>
    get<import("../types").TenantObjectStorageConfig>("/system/object-storage"),

  upsertTenantObjectStorage: (payload: {
    is_enabled: boolean;
    endpoint: string;
    bucket: string;
    access_key: string;
    secret_key?: string;
    secure: boolean;
    region?: string;
  }) => put<import("../types").TenantObjectStorageConfig>("/system/object-storage", payload),

  testTenantObjectStorage: (payload?: {
    is_enabled: boolean;
    endpoint: string;
    bucket: string;
    access_key: string;
    secret_key?: string;
    secure: boolean;
    region?: string;
  }) =>
    post<{ ok: boolean; message: string }>("/system/object-storage/test-connection", payload ?? {}),

  getInfraStatus: () => get<InfraStatus>("/system/infra/status"),

  testInfraConnection: (components?: string[]) =>
    post<{ results: InfraComponentStatus[] }>("/system/infra/test-connection", {
      components: components?.length ? components : undefined,
    }),

  getRedisInfo: () => get<Record<string, unknown>>("/system/infra/redis-info"),

  getWorkerInfo: () => get<Record<string, unknown>>("/system/infra/worker-info"),

  upsertSystemConfig: (key: string, value: unknown, description?: string) =>
    put<{ key: string; value: Record<string, unknown> }>(`/system/configs/${encodeURIComponent(key)}`, {
      value: typeof value === "object" && value !== null ? value : { value },
      description,
    }),

  getSystemQuota: () => get<import("../types").TenantQuota>("/system/quota"),

};
