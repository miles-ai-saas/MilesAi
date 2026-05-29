import type { InfraComponentStatus } from "@/lib/types";

export const SYSTEM_CONFIG_PAGE_DESC =
  "L2 业务参数可在此编辑；L1 部署连接（PostgreSQL / Redis / 对象存储等）来自环境变量，只读展示。";

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
