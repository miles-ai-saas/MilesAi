import { get } from "./client";

export const metaApi = {
  getHookMeta: () => get<import("../types").HookMeta>("/hooks/meta"),

  getComplianceMeta: () => get<import("../types").ComplianceMeta>("/compliance/meta"),

  getFlowMeta: () => get<import("../types").FlowMeta>("/flows/meta"),

  getFlowTemplates: () => get<import("../types").FlowTemplatesResponse>("/flows/templates"),

  getKbMeta: () => get<import("../types").KbMeta>("/kb/meta"),

  getToolsMeta: () => get<import("../types").ToolsMeta>("/tools/meta"),

  getAgentMeta: () => get<import("../types").AgentMeta>("/agents/meta"),

  getPromptMeta: () => get<import("../types").PromptMeta>("/prompt-templates/meta"),

  getSkillMeta: () => get<import("../types").SkillMeta>("/skill-packages/meta"),

  getA2aMeta: () => get<import("../types").A2aMeta>("/a2a/peers/meta"),

  getMonitorMeta: () => get<import("../types").MonitorMeta>("/monitor/meta"),

  getTaskMeta: () => get<import("../types").TaskMeta>("/tasks/meta"),

  getCategoryMeta: () => get<import("../types").CategoryMeta>("/categories/meta"),

  getTagMeta: () => get<import("../types").TagMeta>("/tags/meta"),

  getAuditMeta: () => get<import("../types").AuditMeta>("/audit/meta"),

  getMarketplaceMeta: () => get<import("../types").MarketplaceMeta>("/marketplace/meta"),

  getMcpMeta: () => get<import("../types").McpMeta>("/mcp/meta"),

  getAttachmentMeta: () => get<import("../types").AttachmentMeta>("/attachments/meta"),
};
