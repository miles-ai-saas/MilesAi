export const RISK_PAGE_DESC = "风险事件、IP 黑名单与 API 限流（私有化部署防护）";

export const RATE_LIMIT_SCOPE_LABELS: Record<string, string> = {
  ip: "按来源 IP",
  api_key: "按 API Key",
};

export const EMPTY_RATE_LIMIT_RULE_FORM = {
  name: "",
  path_pattern: "/api/v1/*",
  limit_per_minute: "60",
  scope: "ip" as "ip" | "api_key",
  description: "",
};

export type RateLimitRuleForm = typeof EMPTY_RATE_LIMIT_RULE_FORM;
