"use client";

import { taskStatusBadgeClass, taskStatusLabel } from "@/features/tasks/lib/task-labels";
import type { TaskMeta } from "@/lib/types";

export function TaskStatusBadge({ status, taskMeta }: { status: string; taskMeta: TaskMeta | null }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${taskStatusBadgeClass(status)}`}>
      {taskStatusLabel(status, taskMeta)}
    </span>
  );
}
