/** 工具页共享常量与表单辅助。 */

import { TOOL_PAGE_TABS } from "@/features/tools/lib/tool-labels";
import type { ToolParameterSpec } from "@/lib/types";

export const TOOLS_PAGE_DESC =
  "平台内置与自定义 HTTP / Python 脚本工具；供技能包引用与智能体 function calling。外部 MCP 服务请前往 MCP 工作台。";

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
