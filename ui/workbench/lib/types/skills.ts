/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";
import type { TagRef } from "./tags";
export interface SkillPackage {
  id: string;
  tenant_id?: string;
  category_id?: string | null;
  category_name?: string | null;
  tags?: TagRef[];
  slug: string;
  name: string;
  description?: string | null;
  source_type: string;
  tool_names: string[];
  prompt_snippet?: string | null;
  config: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SkillFileNode {
  name: string;
  path: string;
  type: "file" | "dir";
  children?: SkillFileNode[];
}

export interface SkillImportResult {
  imported: number;
  skipped: number;
  errors: string[];
}
