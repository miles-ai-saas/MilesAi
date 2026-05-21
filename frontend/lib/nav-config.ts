export type AppSection = "workbench" | "system";

export type NavItem = { href: string; label: string };

export type NavGroup = { title: string; items: NavItem[] };

export const APP_SECTIONS: { id: AppSection; label: string; home: string }[] = [
  { id: "workbench", label: "AI 工作台", home: "/workbench" },
  { id: "system", label: "系统管理", home: "/system/users" },
];

export const WORKBENCH_NAV: NavGroup[] = [
  {
    title: "工作台",
    items: [{ href: "/workbench", label: "概览" }],
  },
  {
    title: "智能体",
    items: [
      { href: "/agents", label: "智能体" },
      { href: "/agents/chat", label: "对话工作台" },
    ],
  },
  {
    title: "配置",
    items: [
      { href: "/compliance", label: "合规" },
      { href: "/prompts", label: "提示词模板" },
      { href: "/models", label: "模型供应商" },
      { href: "/hooks", label: "钩子" },
    ],
  },
  {
    title: "能力",
    items: [
      { href: "/tools", label: "工具" },
      { href: "/skills", label: "技能包" },
      { href: "/mcp", label: "MCP" },
    ],
  },
  {
    title: "编排",
    items: [
      { href: "/kb", label: "知识库" },
      { href: "/flows", label: "流程编排" },
    ],
  },
  {
    title: "运营",
    items: [
      { href: "/tasks", label: "任务" },
      { href: "/monitor", label: "监控" },
      { href: "/marketplace", label: "应用市场" },
    ],
  },
];

export const SYSTEM_NAV: NavGroup[] = [
  {
    title: "系统管理",
    items: [
      { href: "/system/users", label: "用户管理" },
      { href: "/system/audit", label: "审计日志" },
    ],
  },
];

export function getAppSection(pathname: string): AppSection {
  if (pathname.startsWith("/system")) return "system";
  return "workbench";
}

export function getNavForSection(section: AppSection): NavGroup[] {
  return section === "system" ? SYSTEM_NAV : WORKBENCH_NAV;
}

export function getOtherSection(current: AppSection) {
  return APP_SECTIONS.find((s) => s.id !== current)!;
}

export function isNavActive(pathname: string, href: string): boolean {
  if (href === "/workbench") {
    return pathname === "/workbench";
  }
  if (href === "/agents") {
    return pathname === "/agents";
  }
  if (href === "/agents/chat") {
    return pathname === "/agents/chat" || pathname.startsWith("/agents/chat/");
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function getPageTitle(pathname: string): string {
  const section = getAppSection(pathname);
  const groups = getNavForSection(section);
  for (const g of groups) {
    const item = g.items.find((i) => isNavActive(pathname, i.href));
    if (item) return item.label;
  }
  return section === "system" ? "系统管理" : "AI 工作台";
}

/** 对话工作台等全屏页无需 main 内边距 */
export function isFullBleedPage(pathname: string): boolean {
  return pathname === "/agents/chat" || pathname.startsWith("/agents/chat/");
}
