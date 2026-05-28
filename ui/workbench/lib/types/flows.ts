/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";
import type { TagRef } from "./tags";
export interface Flow {
  id: string;
  tenant_id: string;
  name: string;
  description?: string | null;
  tags?: TagRef[];
  status: "draft" | "published";
  current_version: number;
  created_at: string;
}

export interface FlowVersionSummary {
  id: string;
  flow_id: string;
  version: number;
  editor_id?: string | null;
  remark?: string | null;
  created_at: string;
}

export interface FlowVersion {
  id: string;
  flow_id: string;
  version: number;
  graph_json: FlowGraph;
  remark?: string | null;
  created_at?: string;
}

export interface FlowGraph {
  nodes: FlowNode[];
  edges: FlowEdge[];
}

export interface FlowNode {
  id: string;
  type: string;
  position?: { x: number; y: number };
  data: Record<string, unknown>;
}

export interface FlowEdge {
  id?: string;
  source: string;
  target: string;
  sourceHandle?: string;
  targetHandle?: string;
}

export interface FlowTemplate {
  id: string;
  label: string;
  hint: string;
  default_name: string;
  insertable: boolean;
  graph_json: FlowGraph;
}

export interface FlowTemplatesResponse {
  items: FlowTemplate[];
}

/** GET /kb/meta */
