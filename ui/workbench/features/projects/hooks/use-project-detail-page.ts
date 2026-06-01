"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { BizDeliverable, BizProject, BizProjectCostSummary, BizProjectMember, BizWorkPackage, TenantUser } from "@/lib/types";

export type ProjectDetailTab = "info" | "workpackages" | "deliverables" | "members" | "cost" | "ai";

export function useProjectDetailPage(projectId: string) {
  const router = useRouter();
  const [project, setProject] = useState<BizProject | null>(null);
  const [deliverables, setDeliverables] = useState<BizDeliverable[]>([]);
  const [members, setMembers] = useState<BizProjectMember[]>([]);
  const [users, setUsers] = useState<TenantUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<ProjectDetailTab>("info");
  const [costSummary, setCostSummary] = useState<BizProjectCostSummary | null>(null);
  const [closing, setClosing] = useState(false);
  const [archiving, setArchiving] = useState(false);

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

  const advanceWpStage = async (wp: BizWorkPackage) => {
    await api.advanceWorkPackageStage(wp.id);
    await refreshProject();
  };

  const loadCostSummary = useCallback(async () => {
    const data = await api.getProjectCostSummary(projectId);
    setCostSummary(data);
    return data;
  }, [projectId]);

  const closeProject = async () => {
    if (!window.confirm("确定结项？结项后项目状态将变为「已结项」。")) return;
    setClosing(true);
    try {
      await api.closeProject(projectId);
      await refreshProject();
    } finally {
      setClosing(false);
    }
  };

  const archiveCase = async (kbId: string) => {
    setArchiving(true);
    try {
      const result = await api.archiveProjectCase(projectId, { kb_id: kbId, run_parse: true });
      alert(`已入库 ${result.archived_count} 份交付物`);
    } finally {
      setArchiving(false);
    }
  };

  const handleTabChange = (t: ProjectDetailTab) => {
    setTab(t);
    if (t === "deliverables") void loadDeliverables();
    if (t === "members") void loadMembers();
    if (t === "cost") void loadCostSummary();
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
    advanceWpStage,
    refreshProject,
    loadDeliverables,
    addMember,
    removeMember,
    costSummary,
    loadCostSummary,
    closeProject,
    archiveCase,
    closing,
    archiving,
  };
}

export type ProjectDetailPageVm = ReturnType<typeof useProjectDetailPage>;
