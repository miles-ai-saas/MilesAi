/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";
import type { TagRef } from "./tags";
export interface PromptTemplate {
  id: string;
  category_id?: string | null;
  category_name?: string | null;
  tags?: TagRef[];
  name: string;
  description?: string | null;
  content: string;
  is_active: boolean;
  created_at: string;
}

