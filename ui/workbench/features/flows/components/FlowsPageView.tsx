"use client";

import { FlowCreateDialog } from "@/features/flows/components/FlowCreateDialog";
import { FlowDetailDialog } from "@/features/flows/components/FlowDetailDialog";
import { FlowMetaDialog } from "@/features/flows/components/FlowMetaDialog";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { TagChips } from "@/components/tag/TagChips";
import { TagFilterDropdown } from "@/components/tag/TagFilterDropdown";
import { TagManageDialog } from "@/components/tag/TagManageDialog";
import type { FlowsPageVm } from "@/features/flows/hooks/use-flows-page";
import { flowStatusLabel } from "@/features/flows/lib/flow-labels";

const FLOWS_PAGE_DESC = "可视化编排智能体执行流程，支持 RAG、工具调用等节点，发布后可绑定智能体。";

export function FlowsPageView({ vm }: { vm: FlowsPageVm }) {
  const {
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
  } = vm;

  return (
    <>
      <ResourceListLayout
        title="流程编排"
        description={FLOWS_PAGE_DESC}
        searchPlaceholder="搜索流程名称或描述"
        search={search}
        onSearchChange={setSearch}
        loading={!ready || list.loading}
        headerAction={
          <div className="flex flex-wrap items-center gap-2">
            <TagFilterDropdown value={tagFilterIds} onChange={setTagFilterIds} />
            <button type="button" className="btn-sm-outline" onClick={() => setTagManageOpen(true)}>
              管理标签
            </button>
          </div>
        }
        footer={
          ready && !list.loading ? (
            <ResourceListFooter page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
          ) : null
        }
      >
        <AddResourceCard label="添加新流程" hint="填写名称、描述与标签，选择画布模板" onClick={() => setCreateOpen(true)} />
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

      <FlowCreateDialog open={createOpen} busy={creating} onClose={() => setCreateOpen(false)} onCreate={onCreate} />

      <FlowMetaDialog
        open={Boolean(metaTarget)}
        initialName={metaTarget?.name ?? ""}
        initialDescription={metaTarget?.description}
        initialTagIds={metaTarget?.tags?.map((t) => t.id) ?? []}
        onClose={() => setMetaTarget(null)}
        onSave={(name, description, tagIds) => saveFlowMeta(metaTarget!.id, name, description, tagIds)}
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
