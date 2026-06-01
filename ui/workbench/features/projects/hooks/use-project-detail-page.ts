"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { BizDeliverable, BizProject, BizProjectMember, BizWorkPackage, TenantUser } from "@/lib/types";

export type ProjectDetailTab = "info" | "workpackages" | "deliverables" | "members" | "ai";

export function useProjectDetailPage(projectId: string) {
  const router = useRouter();
  const [project, setProject] = useState<BizProject | null>(null);
  const [deliverables, setDeliverables] = useState<BizDeliverable[]>([]);
  const [members, setMembers] = useState<BizProjectMember[]>([]);
  const [users, setUsers] = useState<TenantUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<ProjectDetailTab>("info");

  const refreshProject = useCallback(async () => {
    const updated = await api.getProject(projectId);
    setProject(updated);
    return updated;
  }, [projectId]);

  const loadDeliverables = useCallback(() => api.listDeliverables(projectId).then(setDeliverables), [projectId]);
  const loadMembers = useCallback(() => api.listProjectMembers(projectId).then(setMembers), [projectId]);

  useEffect(() => {
    api.getProject(projectId)
      .then(setProject)
      .catch((e) => setError(e?.message ?? "加载失败"))
      .finally(() => setLoading(false));
  }, [projectId]);

  useEffect(() => {
    if (tab !== "members") return;
    void loadMembers();
    void api.listUsers(1, 200).then((r) => setUsers(r.items));
  }, [tab, loadMembers]);

  const updateWpStatus = async (wp: BizWorkPackage, nextStatus: string) => {
    await api.updateWorkPackage(projectId, wp.id, { status: nextStatus });
    await refreshProject();
  };

  const handleTabChange = (t: ProjectDetailTab) => {
    setTab(t);
    if (t === "deliverables") void loadDeliverables();
    if (t === "members") void loadMembers();
  };

  const addMember = async (userId: string, role: string) => {
    await api.addProjectMember(projectId, { user_id: userId, role_in_project: role });
    await loadMembers();
  };

  const removeMember = async (userId: string) => {
    if (!window.confirm("确定移除该成员？")) return;
    await api.removeProjectMember(projectId, userId);
    await loadMembers();
  };

  return {
    router,
    project,
    deliverables,
    members,
    users,
    loading,
    error,
    tab,
    projectId,
    handleTabChange,
    updateWpStatus,
    refreshProject,
    loadDeliverables,
    addMember,
    removeMember,
  };
}

export type ProjectDetailPageVm = ReturnType<typeof useProjectDetailPage>;
