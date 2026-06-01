"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { FlowMetaDialog } from "@/features/flows/components/FlowMetaDialog";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { TagChips } from "@/components/tag/TagChips";
import { TagFilterDropdown } from "@/components/tag/TagFilterDropdown";
import { TagManageDialog } from "@/components/tag/TagManageDialog";
import { TagPicker } from "@/components/tag/TagPicker";
import { useFlowTemplates } from "@/features/flows/hooks/use-flow-templates";
import type { FlowsPageVm } from "@/features/flows/hooks/use-flows-page";
import { flowStatusLabel } from "@/features/flows/lib/flow-labels";
import { api } from "@/lib/api";
import type { Flow, FlowGraph, FlowMeta, FlowTemplate } from "@/lib/types";

const FlowCanvasPreview = dynamic(() => import("@/features/flows/components/FlowCanvasPreview").then((m) => m.FlowCanvasPreview), { ssr: false });

const FLOWS_PAGE_DESC = "可视化编排智能体执行流程，支持 RAG、工具调用等节点，发布后可绑定智能体。";

function FlowCreateDialog({
  open,
  busy = false,
  initialTemplateId,
  onClose,
  onCreate,
}: {
  open: boolean;
  busy?: boolean;
  initialTemplateId?: string | null;
  onClose: () => void;
  onCreate: (payload: { name: string; description: string; tag_ids: string[]; graph_json: FlowGraph }) => Promise<void>;
}) {
  const { templates, defaultTemplate, loading: templatesLoading } = useFlowTemplates(open);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [templateId, setTemplateId] = useState<string>("rag");
  const [creating, setCreating] = useState(false);

  const selected = templates.find((t) => t.id === templateId) ?? defaultTemplate ?? templates[0] ?? null;

  useEffect(() => {
    if (!open || templates.length === 0) return;
    const preferred = initialTemplateId ? templates.find((t) => t.id === initialTemplateId) : null;
    const initial = preferred ?? defaultTemplate ?? templates[0];
    setTemplateId(initial.id);
    setName(initial.default_name);
    setDescription("");
    setTagIds([]);
  }, [open, templates, defaultTemplate, initialTemplateId]);

  const onTemplateChange = (next: FlowTemplate) => {
    setTemplateId(next.id);
    setName((prev) => {
      const wasDefault = templates.some((t) => t.default_name === prev);
      return wasDefault ? next.default_name : prev;
    });
  };

  const submit = async () => {
    const trimmed = name.trim();
    if (!trimmed || !selected) return;
    setCreating(true);
    try {
      await onCreate({
        name: trimmed,
        description: description.trim(),
        tag_ids: tagIds,
        graph_json: selected.graph_json,
      });
      onClose();
    } finally {
      setCreating(false);
    }
  };

  const disabled = busy || creating || templatesLoading;

  return (
    <ResourceDialog
      open={open}
      title="新建流程"
      description="填写基本信息并选择初始画布模板，创建后可在编辑器中继续编排。"
      size="md"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" disabled={disabled} onClick={onClose}>
            取消
          </button>
          <button type="button" className="btn-primary" disabled={disabled || !name.trim() || !selected} onClick={() => void submit()}>
            {creating ? "创建中…" : "创建并编辑"}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <label className="block text-sm">
          <span className="mb-1 block text-ink-muted">流程名称</span>
          <input
            className="input-field w-full"
            placeholder="流程名称"
            value={name}
            maxLength={128}
            disabled={disabled}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-ink-muted">描述（可选）</span>
          <textarea
            className="input-field min-h-[72px] w-full resize-y"
            placeholder="用途说明，将展示在列表卡片上"
            value={description}
            disabled={disabled}
            rows={2}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-ink-muted">标签</span>
          <TagPicker value={tagIds} onChange={setTagIds} disabled={disabled} />
        </label>
        <fieldset className="space-y-2">
          <legend className="text-sm text-ink-muted">初始模板</legend>
          {templatesLoading && templates.length === 0 ? (
            <p className="text-xs text-ink-muted">加载模板…</p>
          ) : templates.length === 0 ? (
            <p className="text-xs text-ink-muted">模板加载失败，请刷新后重试。</p>
          ) : (
            <div className="space-y-2">
              {templates.map((opt) => (
                <label
                  key={opt.id}
                  className={`flex cursor-pointer gap-3 rounded-lg border px-3 py-2.5 transition-colors ${
                    templateId === opt.id ? "border-brand/40 bg-brand-light/20" : "border-line hover:border-line/80"
                  }`}
                >
                  <input
                    type="radio"
                    name="flow-template"
                    className="mt-1 shrink-0"
                    checked={templateId === opt.id}
                    disabled={disabled}
                    onChange={() => onTemplateChange(opt)}
                  />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-ink">{opt.label}</span>
                    <span className="block text-xs text-ink-muted">{opt.hint}</span>
                  </span>
                </label>
              ))}
            </div>
          )}
        </fieldset>
      </div>
    </ResourceDialog>
  );
}

function formatFlowTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function graphStats(graph: FlowGraph | null): { nodes: number; edges: number } {
  if (!graph) return { nodes: 0, edges: 0 };
  return {
    nodes: graph.nodes?.length ?? 0,
    edges: graph.edges?.length ?? 0,
  };
}

function FlowDetailDialog({
  open,
  flow,
  flowMeta,
  publishing = false,
  onClose,
  onEdit,
  onEditMeta,
  onPublish,
}: {
  open: boolean;
  flow: Flow | null;
  flowMeta?: FlowMeta | null;
  publishing?: boolean;
  onClose: () => void;
  onEdit?: () => void;
  onEditMeta?: () => void;
  onPublish?: () => void;
}) {
  const [graph, setGraph] = useState<FlowGraph | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open || !flow) {
      setGraph(null);
      setError("");
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    void api
      .getFlowGraph(flow.id)
      .then((v) => {
        if (!cancelled) setGraph(v.graph_json);
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setGraph(null);
          setError(e instanceof Error ? e.message : "加载画布失败");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, flow]);

  const stats = graphStats(graph);

  return (
    <ResourceDialog
      open={open}
      title={flow?.name ?? "流程详情"}
      size="sheet"
      onClose={onClose}
      footer={
        <div className="flex flex-wrap justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onClose}>
            关闭
          </button>
          {onEditMeta && (
            <button type="button" className="btn-sm-outline" onClick={onEditMeta}>
              编辑信息
            </button>
          )}
          {onPublish && flow && (
            <button
              type="button"
              className="btn-sm-outline"
              disabled={publishing || flow.current_version === 0}
              title={flow.current_version === 0 ? "请先在编辑页保存画布" : undefined}
              onClick={onPublish}
            >
              {publishing ? "发布中…" : "发布"}
            </button>
          )}
          {onEdit && (
            <button type="button" className="btn-primary" onClick={onEdit}>
              编辑画布
            </button>
          )}
        </div>
      }
    >
      {!flow ? (
        <p className="text-sm text-ink-muted">未选择流程</p>
      ) : (
        <div className="space-y-6">
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            {flow.description?.trim() && (
              <div className="sm:col-span-2">
                <dt className="text-xs text-ink-muted">描述</dt>
                <dd className="mt-0.5 whitespace-pre-wrap text-ink">{flow.description.trim()}</dd>
              </div>
            )}
            {(flow.tags?.length ?? 0) > 0 && (
              <div className="sm:col-span-2">
                <dt className="text-xs text-ink-muted">标签</dt>
                <dd className="mt-1">
                  <TagChips tags={flow.tags} />
                </dd>
              </div>
            )}
            <div>
              <dt className="text-xs text-ink-muted">状态</dt>
              <dd className="mt-0.5 font-medium text-ink">{flowStatusLabel(flow.status, flowMeta)}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">当前版本</dt>
              <dd className="mt-0.5 font-medium text-ink">v{flow.current_version}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">创建时间</dt>
              <dd className="mt-0.5 text-ink">{formatFlowTime(flow.created_at)}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">画布规模</dt>
              <dd className="mt-0.5 text-ink">{loading ? "加载中…" : `${stats.nodes} 个节点 · ${stats.edges} 条连线`}</dd>
            </div>
          </dl>

          {error && <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

          <div className="overflow-hidden rounded-xl border border-line bg-surface-muted/30">
            <p className="border-b border-line-soft px-4 py-2 text-xs font-medium text-ink-muted">画布预览</p>
            <div className="relative h-[min(52vh,420px)] min-h-[280px]">
              {loading ? (
                <div className="flex h-full items-center justify-center text-sm text-ink-faint">加载画布…</div>
              ) : graph ? (
                <FlowCanvasPreview graph={graph} className="absolute inset-0 h-full w-full" />
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-ink-faint">暂无画布数据</div>
              )}
            </div>
          </div>
        </div>
      )}
    </ResourceDialog>
  );
}

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
    templateFromUrl,
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

      <FlowCreateDialog open={createOpen} busy={creating} initialTemplateId={templateFromUrl} onClose={() => setCreateOpen(false)} onCreate={onCreate} />

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
