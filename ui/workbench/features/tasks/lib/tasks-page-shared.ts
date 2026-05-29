export type TaskCategory = "celery" | "generative";

export const TASK_CATEGORY_TABS: { key: TaskCategory; label: string }[] = [
  { key: "celery", label: "后台任务" },
  { key: "generative", label: "生成任务" },
];
