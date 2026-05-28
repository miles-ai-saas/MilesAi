/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";
export interface QuotaMetric {
  used: number;
  max: number;
  unit: string;
}

export interface TenantQuota {
  knowledge_bases: QuotaMetric;
  storage_mb: QuotaMetric;
  agents: QuotaMetric;
  flows: QuotaMetric;
  tokens_monthly: QuotaMetric;
  generative_daily: QuotaMetric;
}

export interface Permission {
  id: string;
  code: string;
  name: string;
  module: string;
  description?: string | null;
}

export interface PermissionGroup {
  module: string;
  permissions: Permission[];
}

export interface Role {
  id: string;
  tenant_id?: string | null;
  name: string;
  code: string;
  description?: string | null;
  is_system: boolean;
  permission_codes: string[];
}

export interface ConfigDefinition {
  key: string;
  label: string;
  category: string;
  description: string;
  value_type: string;
  default_value: unknown;
}

export interface InfraComponentStatus {
  id: string;
  label: string;
  status: "ok" | "unavailable" | "skipped";
  latency_ms?: number | null;
  message?: string | null;
}

export interface TenantObjectStorageConfig {
  tenant_id: string;
  is_enabled: boolean;
  endpoint: string;
  bucket: string;
  access_key: string;
  secret_key_masked?: string | null;
  secure: boolean;
  region?: string | null;
  source: "platform" | "tenant";
}

export interface InfraStatus {
  healthy: boolean;
  status: string;
  components: InfraComponentStatus[];
  settings_preview: Record<string, string | null>;
}

export interface RuntimeInfo {
  components: Record<string, string>;
  settings_preview: Record<string, string | number | boolean | null>;
}
