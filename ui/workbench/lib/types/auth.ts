/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";
export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}


export interface UserInfo {
  id: string;
  username: string;
  email: string;
  tenant_id: string;
  is_superuser: boolean;
  permissions: string[];
}


export interface TenantUser {
  id: string;
  username: string;
  email: string;
  phone?: string | null;
  tenant_id: string;
  is_active: boolean;
  is_superuser: boolean;
  role_codes: string[];
}


export interface UserSession {
  jti: string;
  user_agent?: string | null;
  ip?: string | null;
  created_at: string;
  last_seen_at?: string | null;
  is_current: boolean;
}

