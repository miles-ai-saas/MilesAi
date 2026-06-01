"use client";

/** 项目列表页 VM——分页查询、确认删除。 */

import { useCallback, useState } from "react";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useRequireAuth } from "@/lib/auth-store";
import { api } from "@/lib/api";
import type { BizProject } from "@/lib/types";

export function useProjectsPage() {
  const { ready } = useRequireAuth();

  const list = usePagedList(
    (page, size) => api.listProjects(page, size, undefined, undefined),
    { enabled: ready },
  );

  const { requestConfirm, confirmDialog } = useConfirmAction();

  const handleDelete = useCallback(
    (project: BizProject) => {
      requestConfirm({
        title: "删除项目",
        description: `确定删除「${project.name}」？关联的工作包也将一并移除。`,
        onConfirm: async () => {
          await api.deleteProject(project.id);
          list.reload();
        },
      });
    },
    [requestConfirm, list],
  );

  return { ready, list, onDelete: handleDelete, confirmDialog };
}

export type ProjectsPageVm = ReturnType<typeof useProjectsPage>;
