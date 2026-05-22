export type AppSection = "workbench" | "system";

export type NavItem = { href: string; label: string };

export type SystemNavIcon = "users" | "roles" | "config" | "audit";

export type SystemNavItem = NavItem & { icon: SystemNavIcon };

export type BreadcrumbItem = { label: string; href?: string };

export type NavGroup = { title: string; items: NavItem[] };

export const WORKBENCH_PREFIX = "/workbench";

export const APP_SECTIONS: { id: AppSection; label: string; home: string }[] = [
  { id: "workbench", label: "AI 工作台", home: "/workbench/dashboard" },
  { id: "system", label: "系统管理", home: "/system/users" },
];

export const WORKBENCH_NAV: NavGroup[] = [
  {
    title: "工作台",
    items: [{ href: "/workbench/dashboard", label: "概览" }],
  },
  {
    title: "智能体",
    items: [
      { href: "/workbench/agents", label: "智能体" },
      { href: "/workbench/agents/chat", label: "对话工作台" },
    ],
  },
  {
    title: "配置",
    items: [
      { href: "/workbench/compliance", label: "合规" },
      { href: "/workbench/prompts", label: "提示词模板" },
      { href: "/workbench/models", label: "模型供应商" },
      { href: "/workbench/hooks", label: "钩子" },
    ],
  },
  {
    title: "能力",
    items: [
      { href: "/workbench/tools", label: "工具" },
      { href: "/workbench/skills", label: "技能包" },
      { href: "/workbench/mcp", label: "MCP" },
    ],
  },
  {
    title: "编排",
    items: [
      { href: "/workbench/kb", label: "知识库" },
      { href: "/workbench/attachments", label: "附件" },
      { href: "/workbench/flows", label: "流程编排" },
    ],
  },
  {
    title: "运营",
    items: [
      { href: "/workbench/tasks", label: "任务" },
      { href: "/workbench/monitor", label: "监控" },
      { href: "/workbench/marketplace", label: "应用市场" },
    ],
  },
];

export const SYSTEM_NAV: { title: string; items: SystemNavItem[] }[] = [
  {
    title: "权限管理",
    items: [
      { href: "/system/users", label: "用户管理", icon: "users" },
      { href: "/system/roles", label: "角色权限", icon: "roles" },
    ],
  },
  {
    title: "系统设置",
    items: [
      { href: "/system/config", label: "系统配置", icon: "config" },
      { href: "/system/audit", label: "审计日志", icon: "audit" },
    ],
  },
];

export function getSystemBreadcrumbs(pathname: string): BreadcrumbItem[] {
  const home: BreadcrumbItem = { label: "用户管理", href: "/system/users" };

  if (pathname === "/system/users" || pathname === "/system") {
    return [{ label: "用户管理" }];
  }
  if (pathname === "/system/roles") return [home, { label: "角色权限" }];
  if (pathname === "/system/config") return [home, { label: "系统配置" }];
  if (pathname === "/system/audit") return [home, { label: "审计日志" }];

  return [home];
}

export function getAppSection(pathname: string): AppSection {
  if (pathname.startsWith("/system")) return "system";
  return "workbench";
}

export function getNavForSection(
  section: AppSection,
): { title: string; items: NavItem[] }[] {
  return section === "system" ? SYSTEM_NAV : WORKBENCH_NAV;
}

export function getOtherSection(current: AppSection) {
  return APP_SECTIONS.find((s) => s.id !== current)!;
}

export function isNavActive(pathname: string, href: string): boolean {
  if (href === "/workbench/dashboard") {
    return pathname === "/workbench/dashboard" || pathname === "/workbench";
  }
  if (href === "/workbench/agents") {
    return pathname === "/workbench/agents";
  }
  if (href === "/workbench/agents/chat") {
    return (
      pathname === "/workbench/agents/chat" ||
      pathname.startsWith("/workbench/agents/chat/")
    );
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
  return (
    pathname === "/workbench/agents/chat" ||
    pathname.startsWith("/workbench/agents/chat/")
  );
}
