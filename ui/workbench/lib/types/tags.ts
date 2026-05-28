/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";
export type CategoryDomain = "agent" | "prompt" | "skill" | "tool";

export interface SysCategory {
  id: string;
  domain: CategoryDomain;
  parent_id?: string | null;
  name: string;
  slug: string;
  sort_order: number;
  is_system: boolean;
  created_at: string;
}

export interface TagRef {
  id: string;
  name: string;
  slug: string;
}

export interface TenantTag {
  id: string;
  tenant_id: string;
  name: string;
  slug: string;
  created_at: string;
}
