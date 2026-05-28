import type { TaskRecord } from "../types";
import { get, getPage, post } from "./client";
import { buildPageQuery, DEFAULT_PAGE_SIZE } from "../pagination";

export const tasksApi = {
  listTasks: (page = 1, size = DEFAULT_PAGE_SIZE, status?: string) =>
    getPage<TaskRecord>(`/tasks?${buildPageQuery(page, size)}${status ? `&status=${status}` : ""}`),

  getTask: (taskId: string) => get<TaskRecord>(`/tasks/${taskId}`),

  cancelTask: (taskId: string) => post<TaskRecord>(`/tasks/${taskId}/cancel`),

  batchCancelTasks: (taskIds: string[]) =>
    post<{ cancelled: TaskRecord[]; skipped: string[] }>("/tasks/batch-cancel", {
      task_ids: taskIds,
    }),

  retryTask: (taskId: string) => post<TaskRecord>(`/tasks/${taskId}/retry`),
};
