/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";
import type { TagRef } from "./tags";
export interface ToolParameterSpec {
  name: string;
  type: "string" | "number" | "integer" | "boolean";
  description?: string | null;
  required?: boolean;
  default?: unknown;
  enum?: string[];
}


export interface ToolCatalogItem {
  source: "builtin" | "custom" | string;
  slug: string;
  name: string;
  description?: string | null;
  category_id?: string | null;
  category_name?: string | null;
  parameters?: ToolParameterSpec[];
  version?: string | null;
  require_confirmation?: boolean;
  tool_id?: string | null;
  tool_type?: string | null;
  updated_at?: string | null;
}


export interface CustomTool {
  id: string;
  slug: string;
  name: string;
  description?: string | null;
  tool_type: string;
  category_id?: string | null;
  category_name?: string | null;
  tags?: TagRef[];
  version: string;
  require_confirmation: boolean;
  parameters: ToolParameterSpec[];
  config: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}


export interface ToolCreatePayload {
  slug: string;
  name: string;
  description?: string | null;
  tool_type?: "http" | "script";
  category_id?: string | null;
  tag_ids?: string[];
  version?: string;
  require_confirmation?: boolean;
  parameters?: ToolParameterSpec[];
  config: Record<string, unknown>;
}

/** 技能包元数据；正文在服务端磁盘 SKILL.md（slug 为目录名）。 */
