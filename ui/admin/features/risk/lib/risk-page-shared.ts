export const RISK_PAGE_DESC = "风险事件、IP 黑名单与 API 限流（私有化部署防护）";

export const EMPTY_RATE_LIMIT_RULE_FORM = {
  name: "",
  path_pattern: "/api/v1/*",
  limit_per_minute: "60",
  description: "",
};

export type RateLimitRuleForm = typeof EMPTY_RATE_LIMIT_RULE_FORM;
