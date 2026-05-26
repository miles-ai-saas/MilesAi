"use client";

/** 标准列表页范例（链路 §3）：`useRequireAuth` → `usePagedList` → `ResourceListLayout` → `useFlowMeta`。 */

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { FlowCreateDialog } from "@/components/flow/FlowCreateDialog";
import { FlowDetailDialog } from "@/components/flow/FlowDetailDialog";
import { FlowMetaDialog } from "@/components/flow/FlowMetaDialog";
import { CardActions } from "@/components/resource/CardActions";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { TagChips } from "@/components/tag/TagChips";
import { TagFilterSelect } from "@/components/tag/TagFilterSelect";
import { TagManageDialog } from "@/components/tag/TagManageDialog";
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
  const [tagFilterIds, setTagFilterIds] = useState<string[]>([]);
  const [tagManageOpen, setTagManageOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [publishingId, setPublishingId] = useState<string | null>(null);
  const [viewing, setViewing] = useState<Flow | null>(null);
  const [metaTarget, setMetaTarget] = useState<Flow | null>(null);

  const list = usePagedList(
    useCallback(
      (p, s) => api.listFlows(p, s, tagFilterIds.length ? tagFilterIds : undefined),
      [tagFilterIds],
    ),
    { enabled: ready, resetKey: tagFilterIds.join(",") },
  );

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (f) => `${f.name} ${f.description ?? ""}`),
    [list.items, search],
  );

  const openEdit = (flow: Flow) => {
    router.push(`/workbench/flows/${flow.id}/edit`);
  };

  const saveFlowMeta = async (
    flowId: string,
    name: string,
    description: string,
    tagIds: string[],
  ) => {
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

  return (
    <>
      <ResourceListLayout
        title="流程编排"
        description="可视化编排智能体执行流程，支持 RAG、工具调用等节点，发布后可绑定智能体。"
        searchPlaceholder="搜索流程名称或描述"
        search={search}
        onSearchChange={setSearch}
        loading={!ready || list.loading}
        headerAction={
          <div className="flex flex-wrap items-center gap-2">
            <TagFilterSelect value={tagFilterIds} onChange={setTagFilterIds} />
            <button
              type="button"
              className="btn-sm-outline"
              onClick={() => setTagManageOpen(true)}
            >
              管理标签
            </button>
          </div>
        }
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
          hint="填写名称、描述与标签，选择画布模板"
          onClick={() => setCreateOpen(true)}
        />
        {filtered.map((flow) => (
          <ResourceItemCard
            key={flow.id}
            title={flow.name}
            description={flow.description?.trim() || "未填写描述"}
            badge={flowStatusLabel(flow.status, flowMeta)}
            meta={
              <div className="space-y-2">
                <span className="text-xs text-ink-muted">版本 v{flow.current_version}</span>
                <TagChips tags={flow.tags} />
              </div>
            }
            actions={
              <CardActions
                actions={[
                  { label: "详情", onClick: () => setViewing(flow) },
                  { label: "基本信息", onClick: () => setMetaTarget(flow) },
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

      <FlowCreateDialog
        open={createOpen}
        busy={creating}
        onClose={() => setCreateOpen(false)}
        onCreate={async (payload) => {
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
        }}
      />

      <FlowMetaDialog
        open={Boolean(metaTarget)}
        initialName={metaTarget?.name ?? ""}
        initialDescription={metaTarget?.description}
        initialTagIds={metaTarget?.tags?.map((t) => t.id) ?? []}
        onClose={() => setMetaTarget(null)}
        onSave={(name, description, tagIds) =>
          saveFlowMeta(metaTarget!.id, name, description, tagIds)
        }
      />

      <FlowDetailDialog
        open={Boolean(viewing)}
        flow={viewing}
        flowMeta={flowMeta}
        publishing={viewing ? publishingId === viewing.id : false}
        onClose={() => setViewing(null)}
        onEditMeta={viewing ? () => setMetaTarget(viewing) : undefined}
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

      <TagManageDialog open={tagManageOpen} onClose={() => setTagManageOpen(false)} />

      {confirmDialog}
    </>
  );
}
