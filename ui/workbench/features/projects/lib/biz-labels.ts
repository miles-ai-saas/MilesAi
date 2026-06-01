export const PROJECT_STATUS_LABELS: Record<string, string> = {
  draft: "草稿", active: "进行中", on_hold: "暂停",
  delivered: "已交付", closed: "已结项", cancelled: "已取消",
};

export const SERVICE_LINE_LABELS: Record<string, string> = {
  brand_identity: "品牌形象", video_production: "影视拍摄", exhibition: "展览展示",
  event: "活动策划", training: "会务培训", signage: "标识设计",
  cultural_product: "文创产品", print: "宣传品设计印刷",
};

export const SERVICE_LINES = Object.entries(SERVICE_LINE_LABELS).map(([key, label]) => ({ key, label }));

export const WP_STATUS_LABELS: Record<string, string> = {
  pending: "待开始", in_progress: "进行中", review: "审核中", done: "已完成", cancelled: "已取消",
};

export const DELIV_STATUS_LABELS: Record<string, string> = {
  draft: "草稿", submitted: "已提交", accepted: "已验收", rejected: "已驳回",
};

export const DELIV_TYPE_LABELS: Record<string, string> = {
  document: "文档", image: "图片", video: "视频", design: "设计稿", other: "其他",
};

export const MEMBER_ROLE_LABELS: Record<string, string> = {
  owner: "负责人", editor: "编辑", viewer: "只读",
};

export const AI_CARDS = [
  { label: "AI 对话", desc: "在智能体中生成文案、脚本、设计说明", href: "/workbench/agents/chat", icon: "💬" },
  { label: "知识库管理", desc: "管理品牌手册、参考资料库", href: "/workbench/knowledge-base", icon: "📚" },
  { label: "工作流编排", desc: "编排审批、创作流水线", href: "/workbench/flows", icon: "🔄" },
];
