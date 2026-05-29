export const ADMIN_ROLES = [
  { value: "ops", label: "运营 (ops)" },
  { value: "billing", label: "计费 (billing)" },
  { value: "security", label: "安全 (security)" },
  { value: "viewer", label: "只读 (viewer)" },
  { value: "super_admin", label: "超级管理员" },
] as const;

export const ADMINS_PAGE_DESCRIPTION = "创建运营账号、分配角色与重置密码";

export const ADMINS_FORBIDDEN_DESCRIPTION = "仅超级管理员可访问";
