/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";
export interface A2aPeerRefInput {
  peer_id: string;
  role_hint?: string | null;
  trigger_keywords?: string[];
  enabled?: boolean;
}


export interface A2aPeerRef {
  id: string;
  name: string;
  role_hint?: string | null;
  trigger_keywords: string[];
  enabled: boolean;
  status: string;
  card_display_name?: string | null;
  agent_card_url?: string | null;
}


export interface A2aPeer {
  id: string;
  name: string;
  description?: string | null;
  base_url?: string | null;
  agent_card_url: string;
  card_display_name?: string | null;
  status: string;
  skills_count: number;
  last_synced_at?: string | null;
  last_error?: string | null;
  created_at: string;
}


export interface A2aPeerProbeResult {
  ok: boolean;
  card_url: string;
  card_display_name?: string | null;
  skills_count: number;
  message: string;
}


export interface A2aPeerSyncResult {
  peer: A2aPeer;
  card_url: string;
  message: string;
}

