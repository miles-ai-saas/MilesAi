"use client";

import { useTasksCeleryList } from "@/hooks/use-tasks-celery-list";
import { useTasksNavigation } from "@/hooks/use-tasks-navigation";
import type { TaskCategory } from "@/lib/tasks-page-shared";

export function useTasksPage() {
  const navigation = useTasksNavigation();
  const celery = useTasksCeleryList(navigation.category);

  const setCategory = (next: TaskCategory) => {
    celery.resetOnCategoryChange();
    navigation.setCategory(next);
  };

  return {
    ...celery,
    category: navigation.category,
    setCategory,
    detailTaskId: navigation.detailTaskId,
    openDetail: navigation.openDetail,
    closeDetail: navigation.closeDetail,
  };
}

export type TasksPageVm = ReturnType<typeof useTasksPage>;
