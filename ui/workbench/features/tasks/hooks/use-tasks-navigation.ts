"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { TaskCategory } from "@/features/tasks/lib/tasks-page-shared";

export function useTasksNavigation() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const categoryParam = searchParams.get("category");
  const category: TaskCategory = categoryParam === "generative" ? "generative" : "celery";
  const taskFromUrl = searchParams.get("task");

  const [detailTaskId, setDetailTaskId] = useState<string | null>(null);

  useEffect(() => {
    if (taskFromUrl && category === "celery") setDetailTaskId(taskFromUrl);
  }, [taskFromUrl, category]);

  const setCategory = useCallback(
    (next: TaskCategory) => {
      setDetailTaskId(null);
      const params = new URLSearchParams();
      if (next === "generative") params.set("category", "generative");
      const q = params.toString();
      router.replace(q ? `/workbench/tasks?${q}` : "/workbench/tasks", { scroll: false });
    },
    [router],
  );

  const closeDetail = useCallback(() => {
    setDetailTaskId(null);
    const params = new URLSearchParams(searchParams.toString());
    params.delete("task");
    const q = params.toString();
    router.replace(q ? `/workbench/tasks?${q}` : "/workbench/tasks", { scroll: false });
  }, [router, searchParams]);

  const openDetail = useCallback(
    (id: string) => {
      setDetailTaskId(id);
      const params = new URLSearchParams(searchParams.toString());
      params.set("category", "celery");
      params.set("task", id);
      router.replace(`/workbench/tasks?${params.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

  return { category, setCategory, detailTaskId, openDetail, closeDetail };
}

export type TasksNavigationSlice = ReturnType<typeof useTasksNavigation>;
