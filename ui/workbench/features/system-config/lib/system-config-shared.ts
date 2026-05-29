import type { InfraComponentStatus, TenantObjectStorageConfig } from "@/lib/types";

export const INFRA_PREVIEW_LABELS: Record<string, string> = {
  app_env: "运行环境",
  postgres: "PostgreSQL",
  redis: "Redis",
  object_storage_backend: "对象存储类型",
  object_storage_endpoint: "对象存储端点",
  object_storage_bucket: "存储桶",
  vector_store_backend: "向量库类型",
  vector_store_endpoint: "向量库端点",
  celery_broker: "Celery Broker",
  embedding_backend: "Embedding 后端",
};

export function infraStatusClass(status: InfraComponentStatus["status"]) {
  if (status === "ok") return "bg-emerald-50 text-emerald-800";
  if (status === "skipped") return "bg-surface-muted text-ink-faint";
  return "bg-amber-50 text-amber-800";
}

export function infraStatusLabel(status: InfraComponentStatus["status"]) {
  if (status === "ok") return "正常";
  if (status === "skipped") return "跳过";
  return "不可用";
}

export const emptyOssForm = () => ({
  is_enabled: false,
  endpoint: "",
  bucket: "",
  access_key: "",
  secret_key: "",
  secure: false,
  region: "",
});

export type OssFormState = ReturnType<typeof emptyOssForm>;

export function ossFormFromConfig(cfg: TenantObjectStorageConfig): OssFormState {
  return {
    is_enabled: cfg.is_enabled,
    endpoint: cfg.endpoint ?? "",
    bucket: cfg.bucket ?? "",
    access_key: cfg.access_key ?? "",
    secret_key: "",
    secure: cfg.secure ?? false,
    region: cfg.region ?? "",
  };
}
