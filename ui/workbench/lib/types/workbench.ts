/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";
export interface WorkbenchOverview {
  agents: number;
  kbs: number;
  flows: number;
  prompts: number;
  models: number;
  tasks: number;
}

