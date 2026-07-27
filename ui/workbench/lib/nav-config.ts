/**
 * 路由导航配置（链路 §7）：工作台/业务中心/组织设置分区、侧栏项、面包屑、全幅页面判定。
 * 壳层消费方：`AppShell`、`BusinessShell`、`SystemShell`、`WorkbenchHeaderNav`。
 */

import type { UserInfo } from "./types";
import { hasPermission } from "./permissions";

export type AppSection = "workbench" | "business" | "system";

export type NavItem = { href: string; label: string };

export type SystemNavIcon = "users" | "roles" | "sessions" | "quota" | "config" | "audit";

export type SystemNavItem = NavItem & {
  icon: SystemNavIcon;
  /** RBAC 权限码；无则登录即可见 */
  permission?: string;
};

export type BizNavIcon = "clients" | "projects" | "dashboard" | "opportunities" | "contracts" | "suppliers" | "finance" | "workpackages" | "templates" | "market";

export type BizNavItem = NavItem & {
  icon: BizNavIcon;
  permission?: string;
};

export type BreadcrumbItem = { label: string; href?: string };

export type NavGroup = { title: string; items: NavItem[] };

export const WORKBENCH_PREFIX = "/workbench";

export const APP_SECTIONS: { id: AppSection; label: string; home: string }[] = [
  { id: "workbench", label: "AI 工作台", home: "/workbench/dashboard" },
  { id: "business", label: "业务中心", home: "/business/dashboard" },
  { id: "system", label: "组织设置", home: "/system/users" },
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
      { href: "/workbench/agents/chat/", label: "对话工作台" },
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
      { href: "/workbench/media-assets", label: "生成素材" },
      { href: "/workbench/attachments", label: "附件" },
      { href: "/workbench/flows", label: "流程编排" },
    ],
  },
  {
    title: "观测",
    items: [
      { href: "/workbench/tasks", label: "任务中心" },
      { href: "/workbench/monitor", label: "监控" },
    ],
  },
  {
    title: "应用市场",
    items: [{ href: "/workbench/marketplace", label: "应用市场" }],
  },
];

export const BUSINESS_NAV: { title: string; items: BizNavItem[] }[] = [
  {
    title: "工作总览",
    items: [
      { href: "/business/dashboard", label: "业务工作台", icon: "dashboard", permission: "biz:dashboard:read" },
    ],
  },
  {
    title: "销售漏斗",
    items: [
      { href: "/business/clients", label: "客户", icon: "clients", permission: "biz:client:read" },
      { href: "/business/opportunities", label: "商机", icon: "opportunities", permission: "biz:opportunity:read" },
    ],
  },
  {
    title: "项目交付",
    items: [
      { href: "/business/projects", label: "项目", icon: "projects", permission: "biz:project:read" },
      { href: "/business/work-packages", label: "工作包看板", icon: "workpackages", permission: "biz:project:read" },
      { href: "/business/service-templates", label: "服务线模板", icon: "templates", permission: "biz:project:read" },
      { href: "/business/template-market", label: "模板市场", icon: "market", permission: "biz:project:read" },
    ],
  },
  {
    title: "商务结算",
    items: [
      { href: "/business/contracts", label: "合同", icon: "contracts", permission: "biz:contract:read" },
      { href: "/business/finance", label: "财务概览", icon: "finance", permission: "biz:finance:read" },
    ],
  },
  {
    title: "外包资源",
    items: [
      { href: "/business/suppliers", label: "供应商", icon: "suppliers", permission: "biz:supplier:read" },
    ],
  },
];

export const SYSTEM_NAV: { title: string; items: SystemNavItem[] }[] = [
  {
    title: "权限管理",
    items: [
      { href: "/system/users", label: "用户管理", icon: "users", permission: "system:user:read" },
      { href: "/system/roles", label: "角色权限", icon: "roles", permission: "system:role:read" },
      {
        href: "/system/sessions",
        label: "登录会话",
        icon: "sessions",
        permission: "system:session:read",
      },
    ],
  },
  {
    title: "系统设置",
    items: [
      {
        href: "/system/quota",
        label: "资源配额",
        icon: "quota",
        permission: "system:quota:read",
      },
      { href: "/system/config", label: "系统配置", icon: "config", permission: "system:config:read" },
      { href: "/system/audit", label: "审计日志", icon: "audit", permission: "audit:read" },
    ],
  },
];

/** 按用户权限过滤系统管理侧栏（超管见全部）。 */
export function filterSystemNav(user: UserInfo | null | undefined): { title: string; items: SystemNavItem[] }[] {
  return SYSTEM_NAV.map((group) => ({
    ...group,
    items: group.items.filter((item) => !item.permission || hasPermission(user, item.permission)),
  })).filter((g) => g.items.length > 0);
}

/** 按用户权限过滤业务中心侧栏。 */
export function filterBusinessNav(user: UserInfo | null | undefined): { title: string; items: BizNavItem[] }[] {
  return BUSINESS_NAV.map((group) => ({
    ...group,
    items: group.items.filter((item) => !item.permission || hasPermission(user, item.permission)),
  })).filter((g) => g.items.length > 0);
}

export function getSystemBreadcrumbs(pathname: string): BreadcrumbItem[] {
  const home: BreadcrumbItem = { label: "用户管理", href: "/system/users" };

  if (pathname === "/system/users" || pathname === "/system") {
    return [{ label: "用户管理" }];
  }
  if (pathname === "/system/roles") return [home, { label: "角色权限" }];
  if (pathname === "/system/sessions") return [home, { label: "登录会话" }];
  if (pathname === "/system/quota") return [home, { label: "资源配额" }];
  if (pathname === "/system/config") return [home, { label: "系统配置" }];
  if (pathname === "/system/audit") return [home, { label: "审计日志" }];

  return [home];
}

export function getBusinessBreadcrumbs(pathname: string): BreadcrumbItem[] {
  const home: BreadcrumbItem = { label: "业务工作台", href: "/business/dashboard" };

  if (pathname === "/business/dashboard" || pathname === "/business") {
    return [{ label: "业务工作台" }];
  }
  if (pathname === "/business/clients" || pathname.startsWith("/business/clients/")) {
    return [home, { label: "客户" }];
  }
  if (pathname === "/business/opportunities" || pathname.startsWith("/business/opportunities/")) {
    return [home, { label: "商机" }];
  }
  if (pathname === "/business/projects" || pathname.startsWith("/business/projects/")) {
    return [home, { label: "项目" }];
  }
  if (pathname === "/business/work-packages") {
    return [home, { label: "工作包看板" }];
  }
  if (pathname === "/business/service-templates") {
    return [home, { label: "服务线模板" }];
  }
  if (pathname === "/business/template-market") {
    return [home, { label: "模板市场" }];
  }
  if (pathname === "/business/contracts" || pathname.startsWith("/business/contracts/")) {
    return [home, { label: "合同" }];
  }
  if (pathname === "/business/suppliers" || pathname.startsWith("/business/suppliers/")) {
    return [home, { label: "供应商" }];
  }
  if (pathname === "/business/finance") {
    return [home, { label: "财务概览" }];
  }

  return [home];
}

export function getAppSection(pathname: string): AppSection {
  if (pathname.startsWith("/system")) return "system";
  if (pathname.startsWith("/business")) return "business";
  return "workbench";
}

export function getNavForSection(section: AppSection): NavGroup[] {
  if (section === "system") return SYSTEM_NAV;
  if (section === "business") return BUSINESS_NAV;
  return WORKBENCH_NAV;
}

export function getOtherSections(current: AppSection) {
  return APP_SECTIONS.filter((s) => s.id !== current);
}

export function isNavActive(pathname: string, href: string): boolean {
  if (href === "/workbench/dashboard") {
    return pathname === "/workbench/dashboard" || pathname === "/workbench";
  }
  if (href === "/workbench/agents") {
    return pathname === "/workbench/agents";
  }
  if (href === "/workbench/agents/chat") {
    return pathname === "/workbench/agents/chat" || pathname.startsWith("/workbench/agents/chat/");
  }
  if (href === "/business/dashboard") {
    return pathname === "/business/dashboard" || pathname === "/business";
  }
  if (href === "/business/clients") {
    return pathname === "/business/clients" || pathname.startsWith("/business/clients/");
  }
  if (href === "/business/opportunities") {
    return pathname === "/business/opportunities" || pathname.startsWith("/business/opportunities/");
  }
  if (href === "/business/projects") {
    return pathname === "/business/projects" || pathname.startsWith("/business/projects/");
  }
  if (href === "/business/work-packages") {
    return pathname === "/business/work-packages";
  }
  if (href === "/business/contracts") {
    return pathname === "/business/contracts" || pathname.startsWith("/business/contracts/");
  }
  if (href === "/business/suppliers") {
    return pathname === "/business/suppliers" || pathname.startsWith("/business/suppliers/");
  }
  if (href === "/business/finance") {
    return pathname === "/business/finance";
  }
  if (href === "/business/service-templates") {
    return pathname === "/business/service-templates";
  }
  if (href === "/business/template-market") {
    return pathname === "/business/template-market";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function isNavGroupActive(pathname: string, group: NavGroup): boolean {
  return group.items.some((item) => isNavActive(pathname, item.href));
}

export function getPageTitle(pathname: string): string {
  const section = getAppSection(pathname);
  const groups = section === "system" ? SYSTEM_NAV : section === "business" ? BUSINESS_NAV : WORKBENCH_NAV;
  for (const g of groups) {
    const item = g.items.find((i) => isNavActive(pathname, i.href));
    if (item) return item.label;
  }
  if (section === "system") return "组织设置";
  if (section === "business") return "业务中心";
  return "AI 工作台";
}

const FLOW_EDIT_PATH = /\/workbench\/flows\/[^/]+\/edit\/?$/;

/** 对话工作台、流程画布等全屏页无需 main 内边距 */
export function isFullBleedPage(pathname: string): boolean {
  return pathname === "/workbench/agents/chat" || pathname.startsWith("/workbench/agents/chat/") || FLOW_EDIT_PATH.test(pathname);
}

/** 对话工作台、流程画布编辑页占满 header 以下区域（main 不滚动） */
export function isFullHeightPage(pathname: string): boolean {
  return (
    pathname === "/workbench/agents/chat" ||
    pathname.startsWith("/workbench/agents/chat/") ||
    FLOW_EDIT_PATH.test(pathname)
  );
}
