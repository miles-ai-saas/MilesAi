export type ComplianceTab = "words" | "logs" | "test";

/** 纯 UI Tab，不进 GET /compliance/meta */
export const COMPLIANCE_MAIN_TABS: { key: ComplianceTab; label: string }[] = [
  { key: "words", label: "敏感词库" },
  { key: "logs", label: "拦截日志" },
  { key: "test", label: "在线检测" },
];

export const COMPLIANCE_PAGE_DESC = "按词库管理敏感词条；须在「参与扫描的词库」中勾选后，对话等环节才会进行检测。";
