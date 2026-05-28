/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";
import type { Attachment } from "./attachments";
export interface MediaAsset {
  id: string;
  tenant_id: string;
  attachment_id: string;
  cover_attachment_id?: string | null;
  kind: string;
  source: string;
  source_ref_type: string | null;
  source_ref_id: string | null;
  prompt: string | null;
  model_config_id: string | null;
  title: string | null;
  tags: string[] | null;
  kb_id: string | null;
  kb_document_id: string | null;
  promoted_at: string | null;
  created_by: string;
  created_at: string;
  attachment?: Attachment | null;
  cover_attachment?: Attachment | null;
}
