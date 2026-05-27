/** 运营审计 action 中文标签（私有化交付常用操作） */

const ACTION_LABELS: Record<string, string> = {
  "admin.login": "管理员登录",
  "admin.logout": "管理员登出",
  "admin.change_password": "修改密码",
  "admin.revoke_session": "强制下线会话",
  "admin.create": "创建管理员",
  "admin.update": "更新管理员",
  "admin.disable": "禁用管理员",
  "admin.reset_password": "重置管理员密码",
  "tenant.create": "创建租户",
  "tenant.update": "更新租户",
  "tenant.delete": "删除租户",
  "tenant.quota": "调整租户配额",
  "plan.create": "创建套餐",
  "plan.update": "更新套餐",
  "bill.generate": "生成账单",
  "bill.paid": "标记账单已付",
  "bill.void": "作废账单",
  "risk.resolve": "处理风险事件",
  "ip.blacklist.add": "添加 IP 黑名单",
  "risk.ip.toggle": "切换 IP 黑名单",
  "risk.rule.create": "创建限流规则",
  "risk.rule.update": "更新限流规则",
  "model.create": "创建模型",
  "model.update": "更新模型",
  "model.publish": "发布模型",
  "model.deprecate": "下架模型",
  "model.delete": "删除模型",
  "marketplace.approve": "通过应用审核",
  "marketplace.reject": "驳回应用审核",
  "marketplace_category.create": "创建市场分类",
  "marketplace_category.update": "更新市场分类",
  "marketplace_category.delete": "删除市场分类",
  "category.create": "创建工作台分类",
  "category.update": "更新工作台分类",
  "category.delete": "删除工作台分类",
};

export function auditActionLabel(action: string): string {
  return ACTION_LABELS[action] ?? action;
}

export function auditActionOptions(actions: string[]): { value: string; label: string }[] {
  const merged = Array.from(new Set([...Object.keys(ACTION_LABELS), ...actions])).sort();
  return [{ value: "", label: "全部操作" }, ...merged.map((a) => ({ value: a, label: auditActionLabel(a) }))];
}

/** 日期快捷筛选 */
export type AuditDatePreset = "all" | "today" | "7d" | "30d" | "custom";

export function auditDateRangeFromPreset(
  preset: AuditDatePreset,
  customFrom: string,
  customTo: string,
): { created_from?: string; created_to?: string } {
  if (preset === "all") return {};
  const today = new Date();
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  if (preset === "today") {
    const s = fmt(today);
    return { created_from: s, created_to: s };
  }
  if (preset === "7d" || preset === "30d") {
    const days = preset === "7d" ? 6 : 29;
    const from = new Date(today);
    from.setDate(from.getDate() - days);
    return { created_from: fmt(from), created_to: fmt(today) };
  }
  const range: { created_from?: string; created_to?: string } = {};
  if (customFrom) range.created_from = customFrom;
  if (customTo) range.created_to = customTo;
  return range;
}
