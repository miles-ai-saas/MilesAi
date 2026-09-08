export type AdminNavItem = {
  href: string;
  label: string;
  icon: "dashboard" | "tenants" | "billing" | "bills" | "risk" | "audit" | "profile" | "model" | "review" | "marketplace" | "collection" | "admins";
  superAdminOnly?: boolean;
  platformReviewOnly?: boolean;
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
      { href: "/model-catalog", label: "模型目录", icon: "model" },
      { href: "/marketplace-review", label: "应用审核", icon: "review", platformReviewOnly: true },
      { href: "/marketplace-categories", label: "市场分类", icon: "marketplace" },
      { href: "/sys-categories", label: "工作台分类", icon: "collection" },
      { href: "/billing/plans", label: "套餐管理", icon: "billing" },
      { href: "/billing/bills", label: "账单管理", icon: "bills" },
    ],
  },
  {
    title: "安全合规",
    items: [
      { href: "/risk", label: "风控中心", icon: "risk" },
      { href: "/audit", label: "审计日志", icon: "audit" },
    ],
  },
  {
    title: "系统治理",
    items: [{ href: "/admins", label: "平台管理员", icon: "admins", superAdminOnly: true }],
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
  if (pathname === "/model-catalog/new") {
    return [home, { label: "模型目录", href: "/model-catalog" }, { label: "新建模型" }];
  }
  if (pathname.startsWith("/model-catalog/detail")) {
    return [home, { label: "模型目录", href: "/model-catalog" }, { label: "模型详情" }];
  }
  if (pathname === "/marketplace-review") return [home, { label: "应用审核" }];
  if (pathname === "/marketplace-categories") return [home, { label: "市场分类" }];
  if (pathname === "/sys-categories") return [home, { label: "工作台分类" }];
  if (pathname === "/tenants") return [home, { label: "租户管理" }];
  if (pathname.startsWith("/tenants/detail")) return [home, { label: "租户管理", href: "/tenants" }, { label: "租户详情" }];

  if (pathname === "/billing/plans") return [home, { label: "套餐管理" }];
  if (pathname.startsWith("/billing/plans/detail")) {
    return [home, { label: "套餐管理", href: "/billing/plans" }, { label: "套餐详情" }];
  }
  if (pathname === "/billing/bills") return [home, { label: "账单管理" }];
  if (pathname === "/risk") return [home, { label: "风控中心" }];
  if (pathname === "/audit") return [home, { label: "审计日志" }];
  if (pathname === "/admins") return [home, { label: "平台管理员" }];
  if (pathname === "/profile") return [home, { label: "账号安全" }];

  return [home];
}
