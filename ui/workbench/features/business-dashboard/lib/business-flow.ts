/** 业务中心主链路：侧栏分组、页面 Hero、工作台快捷入口共用。 */

export type BusinessFlowStepId =
  | "dashboard"
  | "clients"
  | "opportunities"
  | "projects"
  | "work-packages"
  | "contracts"
  | "finance"
  | "suppliers";

export type BusinessFlowStep = {
  id: BusinessFlowStepId;
  label: string;
  shortLabel: string;
  href: string;
  description: string;
  permission?: string;
};

/** 主业务链（不含供应商等并行资源） */
export const BUSINESS_MAIN_FLOW: BusinessFlowStep[] = [
  {
    id: "clients",
    label: "客户",
    shortLabel: "客户",
    href: "/business/clients",
    description: "维护甲方与联系人",
    permission: "biz:client:read",
  },
  {
    id: "opportunities",
    label: "商机",
    shortLabel: "商机",
    href: "/business/opportunities",
    description: "跟进销售漏斗与报价",
    permission: "biz:opportunity:read",
  },
  {
    id: "projects",
    label: "项目",
    shortLabel: "项目",
    href: "/business/projects",
    description: "赢单后立项与执行",
    permission: "biz:project:read",
  },
  {
    id: "work-packages",
    label: "工作包",
    shortLabel: "交付",
    href: "/business/work-packages",
    description: "按服务线推进与验收",
    permission: "biz:project:read",
  },
  {
    id: "contracts",
    label: "合同",
    shortLabel: "合同",
    href: "/business/contracts",
    description: "签约与履约条款",
    permission: "biz:contract:read",
  },
  {
    id: "finance",
    label: "财务",
    shortLabel: "回款",
    href: "/business/finance",
    description: "收付款与待办款项",
    permission: "biz:finance:read",
  },
];

export const BUSINESS_RESOURCE_FLOW: BusinessFlowStep = {
  id: "suppliers",
  label: "供应商",
  shortLabel: "资源",
  href: "/business/suppliers",
  description: "外包与协作方",
  permission: "biz:supplier:read",
};

export function getFlowStep(id: BusinessFlowStepId): BusinessFlowStep | undefined {
  if (id === "dashboard") {
    return {
      id: "dashboard",
      label: "业务工作台",
      shortLabel: "总览",
      href: "/business/dashboard",
      description: "待办与链路概览",
      permission: "biz:dashboard:read",
    };
  }
  if (id === "suppliers") return BUSINESS_RESOURCE_FLOW;
  return BUSINESS_MAIN_FLOW.find((s) => s.id === id);
}
