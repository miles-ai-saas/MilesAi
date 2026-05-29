"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useFlowMeta } from "@/hooks/use-flow-meta";
import { filterBySearch } from "@/lib/filter-search";
import type { Flow, FlowGraph } from "@/lib/types";

export function useFlowsPage() {
  const router = useRouter();
  const { ready } = useRequireAuth();
  const flowMeta = useFlowMeta(ready);
  const { requestConfirm, confirmDialog } = useConfirmAction();
  const [search, setSearch] = useState("");
  const [tagFilterIds, setTagFilterIds] = useState<string[]>([]);
  const [tagManageOpen, setTagManageOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [publishingId, setPublishingId] = useState<string | null>(null);
  const [viewing, setViewing] = useState<Flow | null>(null);
  const [metaTarget, setMetaTarget] = useState<Flow | null>(null);

  const list = usePagedList(useCallback((p, s) => api.listFlows(p, s, tagFilterIds.length ? tagFilterIds : undefined), [tagFilterIds]), {
    enabled: ready,
    resetKey: tagFilterIds.join(","),
  });

  const filtered = useMemo(() => filterBySearch(list.items, search, (f) => `${f.name} ${f.description ?? ""}`), [list.items, search]);

  const openEdit = (flow: Flow) => {
    router.push(`/workbench/flows/${flow.id}/edit`);
  };

  const saveFlowMeta = async (flowId: string, name: string, description: string, tagIds: string[]) => {
    const updated = await api.updateFlow(flowId, {
      name,
      description: description || null,
      tag_ids: tagIds,
    });
    if (viewing?.id === flowId) setViewing(updated);
    if (metaTarget?.id === flowId) setMetaTarget(updated);
    await list.reload();
  };

  const onPublish = (flow: Flow) => {
    if (flow.current_version === 0) {
      requestConfirm({
        title: "无法发布",
        message: (
          <>
            流程 <span className="font-medium">{flow.name}</span> 尚无已保存版本，请先在编辑页保存画布后再发布。
          </>
        ),
        confirmLabel: "去编辑",
        onConfirm: () => openEdit(flow),
      });
      return;
    }
    requestConfirm({
      title: "发布流程",
      message: (
        <>
          将当前已保存版本 <span className="font-medium">v{flow.current_version}</span> 标记为已发布，智能体可绑定此流程。
          {flow.status === "published" ? "（将更新为最新已保存版本）" : null}
        </>
      ),
      confirmLabel: "确认发布",
      onConfirm: async () => {
        setPublishingId(flow.id);
        try {
          const updated = await api.publishFlow(flow.id);
          if (viewing?.id === flow.id) setViewing(updated);
          await list.reload();
        } finally {
          setPublishingId(null);
        }
      },
    });
  };

  const onDelete = (flow: Flow) => {
    requestConfirm({
      title: "删除流程",
      message: (
        <>
          确定删除流程 <span className="font-medium">{flow.name}</span>？删除后不可恢复，已绑定该流程的智能体将解除关联。
        </>
      ),
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deleteFlow(flow.id);
        if (viewing?.id === flow.id) setViewing(null);
        if (metaTarget?.id === flow.id) setMetaTarget(null);
        await list.reload();
      },
    });
  };

  const onCreate = async (payload: { name: string; description: string; tag_ids: string[]; graph_json: FlowGraph }) => {
    setCreating(true);
    try {
      const flow = await api.createFlow({
        name: payload.name,
        description: payload.description || null,
        tag_ids: payload.tag_ids,
        graph_json: payload.graph_json,
      });
      router.push(`/workbench/flows/${flow.id}/edit`);
    } finally {
      setCreating(false);
    }
  };

  return {
    ready,
    flowMeta,
    search,
    setSearch,
    tagFilterIds,
    setTagFilterIds,
    tagManageOpen,
    setTagManageOpen,
    createOpen,
    setCreateOpen,
    creating,
    publishingId,
    viewing,
    setViewing,
    metaTarget,
    setMetaTarget,
    list,
    filtered,
    confirmDialog,
    openEdit,
    saveFlowMeta,
    onPublish,
    onDelete,
    onCreate,
  };
}

export type FlowsPageVm = ReturnType<typeof useFlowsPage>;
