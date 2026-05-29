export const SYS_CATEGORY_DOMAINS = [
  { key: "agent", label: "智能体" },
  { key: "prompt", label: "提示词" },
  { key: "skill", label: "技能包" },
  { key: "tool", label: "工具" },
] as const;

export type SysCategoryDomainKey = (typeof SYS_CATEGORY_DOMAINS)[number]["key"];

export const SYS_CATEGORIES_PAGE_DESCRIPTION = "全平台全局 sys_categories，各租户共用；租户不可增删改，个性化请用标签。";
