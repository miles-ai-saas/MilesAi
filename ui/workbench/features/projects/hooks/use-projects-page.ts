"use client";

/** 项目列表页 VM——分页查询、确认删除、新建分步弹窗。 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useRequireAuth } from "@/lib/auth-store";
import { api } from "@/lib/api";
import { EMPTY_PROJECT_FORM, type ProjectFormValues } from "@/features/projects/lib/project-form-options";
import type { BizClient, BizProject } from "@/lib/types";

export function useProjectsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { ready } = useRequireAuth();
  const clientFilter = searchParams.get("client_id") ?? "";
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<ProjectFormValues>(EMPTY_PROJECT_FORM);
  const [clients, setClients] = useState<BizClient[]>([]);
  const [clientsLoading, setClientsLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [createError, setCreateError] = useState("");
  const createParamHandled = useRef(false);

  const list = usePagedList(
    (page, size) => api.listProjects(page, size, clientFilter || undefined, undefined),
    { enabled: ready, resetKey: clientFilter },
  );

  const { requestConfirm, confirmDialog } = useConfirmAction();

  const loadClients = useCallback(async () => {
    setClientsLoading(true);
    try {
      const r = await api.listClients(1, 100);
      setClients(r.items);
    } finally {
      setClientsLoading(false);
    }
  }, []);

  const openCreate = useCallback(
    (preselectedClientId?: string) => {
      setCreateError("");
      setCreateForm({
        ...EMPTY_PROJECT_FORM,
        client_id: preselectedClientId || clientFilter || "",
      });
      setCreateOpen(true);
      void loadClients();
    },
    [loadClients, clientFilter],
  );

  const closeCreate = useCallback(() => {
    setCreateOpen(false);
    setCreateError("");
  }, []);

  /** 从 ?create=1 打开弹窗；用 history.replaceState 清参，避免 router.replace 导致 remount 丢状态 */
  useEffect(() => {
    if (!ready || createParamHandled.current) return;
    if (searchParams.get("create") !== "1") return;
    createParamHandled.current = true;

    const clientId = searchParams.get("client_id") ?? undefined;
    openCreate(clientId);

    const params = new URLSearchParams(searchParams.toString());
    params.delete("create");
    const q = params.toString();
    const nextUrl = q ? `/business/projects?${q}` : "/business/projects";
    window.history.replaceState(window.history.state, "", nextUrl);
  }, [ready, searchParams, openCreate]);

  useEffect(() => {
    if (!ready || !clientFilter || clients.length > 0) return;
    void loadClients();
  }, [ready, clientFilter, clients.length, loadClients]);

  const handleCreateSave = useCallback(async () => {
    if (!createForm.name.trim() || !createForm.client_id) return;
    setSaving(true);
    setCreateError("");
    try {
      const project = await api.createProject({
        client_id: createForm.client_id,
        name: createForm.name.trim(),
        code: createForm.code.trim() || undefined,
        description: createForm.description.trim() || undefined,
        work_packages: createForm.work_packages.filter((w) => w.service_line && w.name.trim()),
      });
      setCreateOpen(false);
      try {
        await list.reload();
      } catch {
        /* 创建已成功，列表刷新失败不阻断跳转 */
      }
      router.push(`/business/projects/${project.id}`);
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }, [createForm, list, router]);

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

  const filterClientName = clientFilter
    ? clients.find((c) => c.id === clientFilter)?.name
    : undefined;

  return {
    ready,
    list,
    onDelete: handleDelete,
    confirmDialog,
    clientFilter,
    filterClientName,
    createOpen,
    closeCreate,
    createForm,
    setCreateForm,
    clients,
    clientsLoading,
    saving,
    createError,
    openCreate,
    handleCreateSave,
  };
}

export type ProjectsPageVm = ReturnType<typeof useProjectsPage>;
