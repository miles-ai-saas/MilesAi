/** 运营审计日志展示：时间、摘要与资源文案（纯函数）。 */

import type { AuditLog } from "@/lib/api";

const RESOURCE_TYPE_LABELS: Record<string, string> = {
  admin: "管理员",
  tenant: "租户",
  model_catalog: "模型",
  marketplace_app: "市场应用",
  marketplace_category: "市场分类",
  sys_category: "工作台分类",
};

const DETAIL_KEY_LABELS: Record<string, string> = {
  username: "用户名",
  name: "名称",
  display_name: "显示名",
  fields: "变更字段",
  event_id: "事件 ID",
  path_pattern: "路径规则",
  limit_per_minute: "限流阈值",
  is_active: "启用状态",
  reason: "原因",
  period_start: "周期开始",
  period_end: "周期结束",
};

export function formatAuditTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-CN");
}

export function shortenId(id: string, head = 8): string {
  if (id.length <= head + 1) return id;
  return `${id.slice(0, head)}…`;
}

export function auditResourceTypeLabel(resourceType: string): string {
  return RESOURCE_TYPE_LABELS[resourceType] ?? resourceType;
}

function formatDetailValue(key: string, value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") {
    if (key === "is_active") return value ? "启用" : "禁用";
    return value ? "是" : "否";
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return "—";
    return value.map((v) => String(v)).join("、");
  }
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function buildDetailFields(detail: Record<string, unknown>) {
  return Object.entries(detail)
    .filter(([, value]) => value !== undefined && value !== null)
    .map(([key, value]) => ({
      label: DETAIL_KEY_LABELS[key] ?? key,
      value: formatDetailValue(key, value),
    }));
}

export function buildAdminAuditLogSummary(log: AuditLog): string {
  const { action, detail, resource_id: resourceId } = log;
  const username = typeof detail.username === "string" ? detail.username : null;
  const name = typeof detail.name === "string" ? detail.name : null;

  switch (action) {
    case "admin.login":
      return "管理员登录运营后台";
    case "admin.logout":
      return "管理员退出登录";
    case "admin.change_password":
      return "修改登录密码";
    case "admin.revoke_session":
      return username ? `强制下线「${username}」` : "强制下线会话";
    case "admin.create":
      return username ? `创建管理员「${username}」` : "创建管理员";
    case "admin.update":
      return username ? `更新管理员「${username}」` : "更新管理员";
    case "admin.disable":
      return username ? `禁用管理员「${username}」` : "禁用管理员";
    case "admin.reset_password":
      return username ? `重置「${username}」密码` : "重置管理员密码";
    case "tenant.create":
      return name ? `创建租户「${name}」` : "创建租户";
    case "tenant.update":
      return name ? `更新租户「${name}」` : "更新租户信息";
    case "tenant.delete":
      return name ? `删除租户「${name}」` : "删除租户";
    case "tenant.quota":
      return name ? `调整租户「${name}」配额` : "调整租户配额";
    case "marketplace.approve":
      return "通过应用审核";
    case "marketplace.reject":
      return typeof detail.reason === "string" && detail.reason ? `驳回应用：${detail.reason}` : "驳回应用审核";
    default: {
      const fields = buildDetailFields(detail);
      if (fields.length > 0) return fields.map((f) => `${f.label}：${f.value}`).slice(0, 2).join(" · ");
      if (resourceId) return `操作资源 ${shortenId(resourceId)}`;
      return "";
    }
  }
}

export function resolveAdminAuditOperatorLabel(log: AuditLog): { label: string; title?: string } {
  if (log.admin_username) return { label: log.admin_username, title: log.admin_id ?? undefined };
  if (log.admin_id) return { label: shortenId(log.admin_id), title: log.admin_id };
  return { label: "系统" };
}
