/** 审计日志展示：摘要与操作者文案（纯函数）。 */

import { shortenId } from "@/features/system-audit/lib/system-audit-shared";
import type { TenantAuditLog } from "@/lib/types";

const DETAIL_KEY_LABELS: Record<string, string> = {
  username: "用户名",
  fields: "变更字段",
  batch: "批量操作",
  is_active: "账号状态",
  role_ids: "角色 ID",
  is_enabled: "启用状态",
  bucket: "存储桶",
  name: "名称",
  title: "标题",
  filename: "文件名",
  version: "版本",
  status: "状态",
};

function formatDetailValue(key: string, value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") {
    if (key === "is_active") return value ? "启用" : "禁用";
    if (key === "is_enabled") return value ? "已开启" : "已关闭";
    if (key === "batch") return value ? "是" : "否";
    return value ? "是" : "否";
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return "—";
    if (key === "role_ids") return value.map((v) => shortenId(String(v), 6)).join("、");
    return value.map((v) => String(v)).join("、");
  }
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function buildAuditDetailFields(detail: Record<string, unknown>) {
  return Object.entries(detail)
    .filter(([, value]) => value !== undefined && value !== null)
    .map(([key, value]) => ({
      label: DETAIL_KEY_LABELS[key] ?? key,
      value: formatDetailValue(key, value),
    }));
}

export function buildAuditLogSummary(log: TenantAuditLog): string {
  const { action, detail, resource_id: resourceId } = log;
  const username = typeof detail.username === "string" ? detail.username : null;

  switch (action) {
    case "user.create":
      return username ? `创建用户「${username}」` : "创建新用户";
    case "user.update":
      if (detail.batch && detail.is_active === true) return "批量启用用户账号";
      if (detail.batch && detail.is_active === false) return "批量禁用用户账号";
      if (detail.batch && Array.isArray(detail.role_ids)) return `批量分配 ${detail.role_ids.length} 个角色`;
      if (Array.isArray(detail.fields) && detail.fields.length > 0) {
        return `更新字段：${detail.fields.map(String).join("、")}`;
      }
      return "更新用户信息";
    case "user.reset_password":
      return "重置用户登录密码";
    case "user.deactivate":
      return detail.batch ? "批量删除用户账号" : "删除用户账号";
    case "auth.login":
      return "用户登录工作台";
    case "agent.create":
      return typeof detail.name === "string" ? `创建智能体「${detail.name}」` : "创建智能体";
    case "agent.update":
      return typeof detail.name === "string" ? `更新智能体「${detail.name}」` : "更新智能体配置";
    case "agent.delete":
      return typeof detail.name === "string" ? `删除智能体「${detail.name}」` : "删除智能体";
    case "kb.document.upload":
      return typeof detail.filename === "string" ? `上传文档「${detail.filename}」` : "上传知识库文档";
    case "kb.document.delete":
      return typeof detail.filename === "string" ? `删除文档「${detail.filename}」` : "删除知识库文档";
    case "flow.publish":
      return typeof detail.version === "string" || typeof detail.version === "number"
        ? `发布流程版本 v${detail.version}`
        : "发布流程新版本";
    case "compliance.scan":
      return "执行合规内容试跑";
    case "config.tenant_object_storage.update": {
      const parts: string[] = [];
      if (typeof detail.is_enabled === "boolean") parts.push(detail.is_enabled ? "开启对象存储" : "关闭对象存储");
      if (typeof detail.bucket === "string" && detail.bucket) parts.push(`桶 ${detail.bucket}`);
      return parts.length > 0 ? parts.join("，") : "更新租户对象存储配置";
    }
    default: {
      const fields = buildAuditDetailFields(detail);
      if (fields.length > 0) return fields.map((f) => `${f.label}：${f.value}`).slice(0, 2).join(" · ");
      if (resourceId) return `操作资源 ${shortenId(resourceId)}`;
      return "";
    }
  }
}

export function resolveAuditOperatorLabel(log: TenantAuditLog): { label: string; title?: string } {
  if (log.username) return { label: log.username, title: log.user_id ?? undefined };
  if (log.user_id) return { label: shortenId(log.user_id), title: log.user_id };
  return { label: "系统" };
}
