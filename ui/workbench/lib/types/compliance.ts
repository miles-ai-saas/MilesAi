/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";
export type SensitiveAction = "warn" | "block";


export interface WordLibrary {
  id: string;
  tenant_id: string;
  name: string;
  description?: string | null;
  is_active: boolean;
  sort_order: number;
  word_count: number;
  created_at: string;
}


export interface LibraryWord {
  id: string;
  library_id: string;
  entry_id: string;
  word: string;
  action: SensitiveAction;
  is_active: boolean;
  created_at: string;
}


export interface EntryLibraryRef {
  library_id: string;
  library_name: string;
  binding_id: string;
  action: SensitiveAction;
  is_active: boolean;
}


export interface SensitiveWordEntry {
  id: string;
  tenant_id: string;
  word: string;
  libraries: EntryLibraryRef[];
  created_at: string;
}


export interface ComplianceScanBindings {
  library_ids: string[];
  libraries: WordLibrary[];
}


export interface ComplianceScanResult {
  blocked: boolean;
  warned: boolean;
  matches: { word: string; action: string }[];
  scanning_enabled: boolean;
}


export interface InterceptLog {
  id: string;
  module: string;
  direction: string;
  matched_word?: string | null;
  action: string;
  content_snippet?: string | null;
  created_at: string;
}

