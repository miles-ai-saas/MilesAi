/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";
export type ModelSource = "builtin" | "custom";

export type ModelCredentialStatus = "platform" | "tenant" | "missing";

export interface ModelConfig {
  id: string;
  source: ModelSource;
  name: string;
  vendor: string;
  provider: string;
  model_name: string;
  model_code?: string | null;
  model_type: string;
  description?: string | null;
  context_window?: string | null;
  badge?: string | null;
  api_base?: string | null;
  is_active: boolean;
  publish_status?: string | null;
  credential_status: ModelCredentialStatus;
  has_api_key: boolean;
  extra?: { embedding_dimension?: number; invoke_mode?: string; litellm_model?: string };
  created_at: string;
}

export interface ModelCatalogMeta {
  vendors: { value: string; label: string }[];
  model_types: { value: string; label: string }[];
}
