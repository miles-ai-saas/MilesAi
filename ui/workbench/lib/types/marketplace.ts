/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";
import type { TagRef } from "./tags";
export interface AppCategory {
  id: string;
  name: string;
  slug: string;
  sort_order: number;
}


export interface MarketplaceApp {
  id: string;
  name: string;
  description?: string | null;
  icon?: string | null;
  version: string;
  status: string;
  is_official: boolean;
  install_count: number;
  rating_avg: number;
  rating_count: number;
  visibility?: string;
  category_id?: string | null;
  category_name?: string | null;
  tags?: TagRef[];
  installed: boolean;
  review_note?: string | null;
  submitted_at?: string | null;
  reviewed_at?: string | null;
  created_at: string;
}


export interface AppRating {
  id: string;
  app_id: string;
  user_id: string;
  score: number;
  comment?: string | null;
  created_at: string;
  updated_at: string;
}


export interface MarketplaceAppDetail extends MarketplaceApp {
  manifest: Record<string, unknown>;
  my_rating?: AppRating | null;
}


export interface AppInstallResult {
  install: {
    id: string;
    app_id: string;
    app_name: string;
    flow_id?: string | null;
    agent_id?: string | null;
    kb_id?: string | null;
  };
  flow_id?: string | null;
  agent_id?: string | null;
  kb_id?: string | null;
  message: string;
}


export interface AppUpgradeResult {
  install: AppInstall;
  previous_version: string;
  new_version: string;
  message: string;
}


export interface UpgradeFieldChange {
  field: string;
  label: string;
  before?: string | null;
  after?: string | null;
  changed: boolean;
}


export interface UpgradeResourceDiff {
  resource_type: string;
  resource_id?: string | null;
  resource_name: string;
  changes: UpgradeFieldChange[];
  has_changes: boolean;
}


export interface AppUpgradePreview {
  app_id: string;
  app_name: string;
  installed_version: string;
  target_version: string;
  can_upgrade: boolean;
  has_changes: boolean;
  message?: string | null;
  resources: UpgradeResourceDiff[];
}


export interface AppRollbackPreview {
  app_id: string;
  app_name: string;
  current_version: string;
  target_version: string;
  can_rollback: boolean;
  message?: string;
  resources: UpgradeResourceDiff[];
}


export interface AppInstall {
  id: string;
  app_id: string;
  app_name: string;
  installed_version?: string;
  app_version?: string | null;
  flow_id?: string | null;
  agent_id?: string | null;
  kb_id?: string | null;
  created_at: string;
}
