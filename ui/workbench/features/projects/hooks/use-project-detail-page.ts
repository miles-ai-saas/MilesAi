"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import type { BizDeliverable, BizProject, BizProjectCostSummary, BizProjectMember, BizWorkPackage, TenantUser } from "@/lib/types";

export type ProjectDetailTab = "info" | "workpackages" | "deliverables" | "members" | "suppliers" | "cost" | "activity" | "ai";

const VALID_TABS: ProjectDetailTab[] = ["info", "workpackages", "deliverables", "members", "suppliers", "cost", "activity", "ai"];

function parseTab(raw: string | null): ProjectDetailTab {
  if (raw && VALID_TABS.includes(raw as ProjectDetailTab)) {
    return raw as ProjectDetailTab;
  }
  return "info";
}

export function useProjectDetailPage(projectId: string) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tab = parseTab(searchParams.get("tab"));

  const [project, setProject] = useState<BizProject | null>(null);
  const [clientName, setClientName] = useState("");
  const [deliverables, setDeliverables] = useState<BizDeliverable[]>([]);
  const [members, setMembers] = useState<BizProjectMember[]>([]);
  const [supplierCount, setSupplierCount] = useState(0);
  const [users, setUsers] = useState<TenantUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [costSummary, setCostSummary] = useState<BizProjectCostSummary | null>(null);
  const [closing, setClosing] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [editingInfo, setEditingInfo] = useState(false);
  const [savingInfo, setSavingInfo] = useState(false);
  const [infoForm, setInfoForm] = useState({
    name: "", code: "", description: "", total_budget: "", status: "draft",
  });

  const refreshProject = useCallback(async () => {
    const updated = await api.getProject(projectId);
    setProject(updated);
    setInfoForm({
      name: updated.name,
      code: updated.code ?? "",
      description: updated.description ?? "",
      total_budget: updated.total_budget != null ? String(updated.total_budget) : "",
      status: updated.status,
    });
    return updated;
  }, [projectId]);

  const loadDeliverables = useCallback(() => api.listDeliverables(projectId).then(setDeliverables), [projectId]);
  const loadMembers = useCallback(() => api.listProjectMembers(projectId).then(setMembers), [projectId]);
  const loadSupplierCount = useCallback(
    () => api.listProjectSuppliers(projectId).then((rows) => setSupplierCount(rows.length)),
    [projectId],
  );
  const loadCostSummary = useCallback(async () => {
    const data = await api.getProjectCostSummary(projectId);
    setCostSummary(data);
    return data;
  }, [projectId]);

  useEffect(() => {
    setLoading(true);
    setError("");
    api.getProject(projectId)
      .then(async (p) => {
        setProject(p);
        setInfoForm({
          name: p.name,
          code: p.code ?? "",
          description: p.description ?? "",
          total_budget: p.total_budget != null ? String(p.total_budget) : "",
          status: p.status,
        });
        try {
          const client = await api.getClient(p.client_id);
          setClientName(client.name);
        } catch {
          setClientName("");
        }
        await Promise.all([loadDeliverables(), loadMembers(), loadSupplierCount()]);
      })
      .catch((e) => setError(e?.message ?? "加载失败"))
      .finally(() => setLoading(false));
  }, [projectId, loadDeliverables, loadMembers, loadSupplierCount]);

  useEffect(() => {
    if (tab === "cost") void loadCostSummary();
    if (tab === "members" && users.length === 0) {
      void api.listUsers(1, 100).then((r) => setUsers(r.items));
    }
  }, [tab, loadCostSummary, users.length]);

  const handleTabChange = useCallback(
    (next: ProjectDetailTab) => {
      const params = new URLSearchParams(searchParams.toString());
      if (next === "info") params.delete("tab");
      else params.set("tab", next);
      const q = params.toString();
      router.replace(`/business/projects/${projectId}${q ? `?${q}` : ""}`, { scroll: false });
    },
    [router, projectId, searchParams],
  );

  const updateWpStatus = async (wp: BizWorkPackage, nextStatus: string) => {
    await api.updateWorkPackage(projectId, wp.id, { status: nextStatus });
    await refreshProject();
  };

  const advanceWpStage = async (wp: BizWorkPackage) => {
    await api.advanceWorkPackageStage(wp.id);
    await refreshProject();
  };

  const rollbackWpStage = async (wp: BizWorkPackage) => {
    if (!window.confirm(`确定将「${wp.name}」回退到上一阶段？`)) return;
    await api.rollbackWorkPackageStage(wp.id);
    await refreshProject();
  };

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

  const saveProjectInfo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!infoForm.name.trim()) return;
    setSavingInfo(true);
    try {
      await api.updateProject(projectId, {
        name: infoForm.name.trim(),
        code: infoForm.code.trim() || undefined,
        description: infoForm.description.trim() || undefined,
        total_budget: infoForm.total_budget ? Number(infoForm.total_budget) : undefined,
        status: infoForm.status,
      });
      await refreshProject();
      setEditingInfo(false);
    } finally {
      setSavingInfo(false);
    }
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

  const pendingDeliverables = deliverables.filter((d) => d.status === "submitted").length;

  return {
    router,
    project,
    clientName,
    deliverables,
    members,
    supplierCount,
    pendingDeliverables,
    users,
    loading,
    error,
    tab,
    projectId,
    handleTabChange,
    updateWpStatus,
    advanceWpStage,
    rollbackWpStage,
    refreshProject,
    loadDeliverables,
    loadMembers,
    loadSupplierCount,
    addMember,
    removeMember,
    costSummary,
    loadCostSummary,
    closeProject,
    archiveCase,
    closing,
    archiving,
    editingInfo,
    setEditingInfo,
    infoForm,
    setInfoForm,
    savingInfo,
    saveProjectInfo,
  };
}

export type ProjectDetailPageVm = ReturnType<typeof useProjectDetailPage>;
