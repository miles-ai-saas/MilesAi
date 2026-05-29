export type TaskCategory = "celery" | "generative";

export const TASK_CATEGORY_TABS: { key: TaskCategory; label: string }[] = [
  { key: "celery", label: "后台任务" },
  { key: "generative", label: "生成任务" },
];

export const TASKS_PAGE_DESC: Record<TaskCategory, string> = {
  celery: "文档入库等 Celery 异步任务；支持按状态筛选、搜索、取消与重试；点击「刷新」更新列表。",
  generative: "智能体对话、流程或 API 触发的生图/生视频任务；支持类型筛选、进度查看、取消与失败重试；可跳转关联的后台 Celery 记录；点击「刷新」更新列表。",
};
