/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";
export interface Attachment {
  id: string;
  tenant_id: string;
  uploaded_by: string;
  filename: string;
  mime_type: string;
  file_size: number;
  object_bucket: string;
  purpose: string;
  resource_type: string | null;
  resource_id: string | null;
  created_at: string;
}

/** AI 生成物媒体资产（blob 在 attachment） */
