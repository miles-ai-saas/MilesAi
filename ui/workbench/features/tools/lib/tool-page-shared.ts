/** 工具页共享常量与表单辅助。 */

import { TOOL_PAGE_TABS } from "@/features/tools/lib/tool-labels";
import type { ToolParameterSpec } from "@/lib/types";

export const TOOLS_MAIN_TABS = TOOL_PAGE_TABS.map((t) => ({ key: t.key, label: t.label }));

export function slugFromName(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 63);
}

export const defaultToolParams = (): ToolParameterSpec[] => [];
