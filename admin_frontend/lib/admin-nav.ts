export type AdminNavItem = {
  href: string;
  label: string;
  icon: "dashboard" | "tenants" | "billing" | "risk" | "audit" | "profile" | "catalog";
};

export type AdminNavGroup = {
  title: string;
  items: AdminNavItem[];
};

export const ADMIN_NAV: AdminNavGroup[] = [
  {
    title: "总览",
    items: [{ href: "/", label: "控制台", icon: "dashboard" }],
  },
  {
    title: "业务运营",
    items: [
      { href: "/tenants", label: "租户管理", icon: "tenants" },
      { href: "/model-catalog", label: "模型目录", icon: "catalog" },
      { href: "/marketplace-categories", label: "市场分类", icon: "catalog" },
      { href: "/sys-categories", label: "工作台分类", icon: "catalog" },
      { href: "/billing", label: "计费管理", icon: "billing" },
    ],
  },
  {
    title: "安全合规",
    items: [
      { href: "/risk", label: "风控中心", icon: "risk" },
      { href: "/audit", label: "审计日志", icon: "audit" },
    ],
  },
];

export const ADMIN_ACCOUNT_NAV: AdminNavItem = {
  href: "/profile",
  label: "账号安全",
  icon: "profile",
};

export function isAdminNavActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export type BreadcrumbItem = { label: string; href?: string };

export function getAdminBreadcrumbs(pathname: string): BreadcrumbItem[] {
  const home: BreadcrumbItem = { label: "控制台", href: "/" };

  if (pathname === "/") return [{ label: "控制台" }];

  if (pathname === "/model-catalog") return [home, { label: "模型目录" }];
  if (pathname === "/marketplace-categories") return [home, { label: "市场分类" }];
  if (pathname === "/sys-categories") return [home, { label: "工作台分类" }];
  if (pathname === "/tenants") return [home, { label: "租户管理" }];
  if (pathname.startsWith("/tenants/")) return [home, { label: "租户管理", href: "/tenants" }, { label: "租户详情" }];

  if (pathname === "/billing") return [home, { label: "计费管理" }];
  if (pathname === "/risk") return [home, { label: "风控中心" }];
  if (pathname === "/audit") return [home, { label: "审计日志" }];
  if (pathname === "/profile") return [home, { label: "账号安全" }];

  return [home];
}
