"use client";

/** 标准列表页范例（链路 §3）：`useRequireAuth` → `usePagedList` → `ResourceListLayout` → `useFlowMeta`。 */

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { FlowDetailDialog } from "@/components/flow/FlowDetailDialog";
import { CardActions } from "@/components/resource/CardActions";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { RAG_TEMPLATE } from "@/lib/flow-nodes";
import { flowStatusLabel } from "@/lib/flow-labels";
import { filterBySearch } from "@/lib/filter-search";
import { useFlowMeta } from "@/hooks/use-flow-meta";
import type { Flow } from "@/lib/types";

export default function FlowsPage() {
  const router = useRouter();
  const { ready } = useRequireAuth();
  const flowMeta = useFlowMeta(ready);
  const { requestConfirm, confirmDialog } = useConfirmAction();
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [publishingId, setPublishingId] = useState<string | null>(null);
  const [viewing, setViewing] = useState<Flow | null>(null);

  const list = usePagedList(useCallback((p, s) => api.listFlows(p, s), []), { enabled: ready });

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (f) => `${f.name} ${f.description ?? ""}`),
    [list.items, search],
  );

  const createRagFlow = async () => {
    setCreating(true);
    try {
      const flow = await api.createFlow("RAG 问答流程", RAG_TEMPLATE);
      router.push(`/workbench/flows/${flow.id}/edit`);
    } finally {
      setCreating(false);
    }
  };

  const openEdit = (flow: Flow) => {
    router.push(`/workbench/flows/${flow.id}/edit`);
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
        await list.reload();
      },
    });
  };

  return (
    <>
      <ResourceListLayout
        title="流程编排"
        description="可视化编排智能体执行流程，支持 RAG、工具调用等节点，发布后可绑定智能体。"
        searchPlaceholder="搜索流程名称"
        search={search}
        onSearchChange={setSearch}
        loading={!ready || list.loading}
        footer={
          ready && !list.loading ? (
            <ResourceListFooter
              page={list.page}
              size={list.size}
              total={list.total}
              onPageChange={list.setPage}
            />
          ) : null
        }
      >
        <AddResourceCard
          label="添加新流程"
          hint={creating ? "创建中…" : "从 RAG 模板快速创建"}
          onClick={createRagFlow}
        />
        {filtered.map((flow) => (
          <ResourceItemCard
            key={flow.id}
            title={flow.name}
            description={flow.description ?? "未填写描述"}
            badge={flowStatusLabel(flow.status, flowMeta)}
            meta={
              <span className="text-xs text-ink-muted">
                版本 v{flow.current_version}
              </span>
            }
            actions={
              <CardActions
                actions={[
                  { label: "详情", onClick: () => setViewing(flow) },
                  {
                    label: publishingId === flow.id ? "发布中…" : "发布",
                    disabled: publishingId === flow.id || flow.current_version === 0,
                    onClick: () => onPublish(flow),
                  },
                  {
                    label: "编辑画布",
                    variant: "primary",
                    onClick: () => openEdit(flow),
                  },
                ]}
                onDelete={() => onDelete(flow)}
              />
            }
          />
        ))}
      </ResourceListLayout>

      <FlowDetailDialog
        open={Boolean(viewing)}
        flow={viewing}
        flowMeta={flowMeta}
        publishing={viewing ? publishingId === viewing.id : false}
        onClose={() => setViewing(null)}
        onPublish={viewing ? () => onPublish(viewing) : undefined}
        onEdit={
          viewing
            ? () => {
                setViewing(null);
                openEdit(viewing);
              }
            : undefined
        }
      />

      {confirmDialog}
    </>
  );
}
