"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useRequireAuth } from "@/lib/auth-store";
import { api } from "@/lib/api";
import { useBizDetailQuery } from "@/features/business/lib/use-biz-detail-query";
import { EMPTY_CONTRACT_FORM, type ContractFormValues } from "@/features/contracts/lib/contract-form-options";
import type { BizClient, BizContract, BizProject } from "@/lib/types";

export function useContractsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { ready } = useRequireAuth();
  const { detailId, openDetail, closeDetail } = useBizDetailQuery("/business/contracts");
  const list = usePagedList((page, size) => api.listContracts(page, size), { enabled: ready });
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<ContractFormValues>(EMPTY_CONTRACT_FORM);
  const [projects, setProjects] = useState<BizProject[]>([]);
  const [clients, setClients] = useState<BizClient[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const prefillHandled = useRef(false);

  const openCreate = useCallback(
    (preselected?: { projectId?: string; clientId?: string }) => {
      setCreateForm({
        ...EMPTY_CONTRACT_FORM,
        project_id: preselected?.projectId ?? "",
        client_id: preselected?.clientId ?? "",
      });
      setCreateOpen(true);
      void (async () => {
        setOptionsLoading(true);
        try {
          const [projectRes, clientRes] = await Promise.all([
            api.listProjects(1, 100),
            api.listClients(1, 100),
          ]);
          setProjects(projectRes.items);
          setClients(clientRes.items);
          if (preselected?.projectId && !preselected.clientId) {
            const project = projectRes.items.find((p) => p.id === preselected.projectId);
            if (project) {
              setCreateForm((prev) => ({ ...prev, project_id: project.id, client_id: project.client_id }));
            }
          }
        } finally {
          setOptionsLoading(false);
        }
      })();
    },
    [],
  );

  useEffect(() => {
    if (!ready || prefillHandled.current) return;
    const projectId = searchParams.get("project_id");
    const clientId = searchParams.get("client_id");
    if (!projectId && !clientId) return;
    prefillHandled.current = true;
    openCreate({ projectId: projectId ?? undefined, clientId: clientId ?? undefined });
    router.replace("/business/contracts");
  }, [ready, searchParams, openCreate, router]);

  const handleCreateSave = useCallback(async () => {
    if (!createForm.name.trim() || !createForm.project_id || !createForm.client_id) return;
    setSaving(true);
    try {
      const c = await api.createContract({
        project_id: createForm.project_id,
        client_id: createForm.client_id,
        name: createForm.name.trim(),
        contract_no: createForm.contract_no.trim() || undefined,
        type: createForm.type,
        total_amount: createForm.total_amount ? Number(createForm.total_amount) : undefined,
        payment_terms: createForm.payment_terms.trim() || undefined,
        description: createForm.description.trim() || undefined,
      });
      setCreateOpen(false);
      await list.reload();
      openDetail(c.id);
    } finally {
      setSaving(false);
    }
  }, [createForm, list, openDetail]);

  const handleDelete = useCallback(
    (c: BizContract) => requestConfirm({
      title: "删除合同",
      description: `确定删除「${c.name}」？`,
      onConfirm: async () => {
        await api.deleteContract(c.id);
        if (detailId === c.id) closeDetail();
        list.reload();
      },
    }),
    [requestConfirm, list, detailId, closeDetail],
  );

  return {
    ready,
    list,
    onDelete: handleDelete,
    confirmDialog,
    createOpen,
    setCreateOpen,
    createForm,
    setCreateForm,
    projects,
    clients,
    optionsLoading,
    saving,
    openCreate,
    handleCreateSave,
    detailId,
    openDetail,
    closeDetail,
  };
}

export type ContractsPageVm = ReturnType<typeof useContractsPage>;
