"use client";

/** 任务中心：后台 Celery 任务 + 生成任务（generative_jobs）。 */

import { Suspense } from "react";
import { TasksPageView } from "@/components/task/TasksPageView";
import { useTasksPage } from "@/hooks/use-tasks-page";

function TasksPageContent() {
  const vm = useTasksPage();
  return <TasksPageView vm={vm} />;
}

export default function TasksPage() {
  return (
    <Suspense fallback={<div className="py-12 text-center text-sm text-ink-muted">加载任务列表…</div>}>
      <TasksPageContent />
    </Suspense>
  );
}
