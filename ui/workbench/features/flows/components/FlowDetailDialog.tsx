"use client";

/** 流程列表「查看详情」：元信息 + 画布只读预览（链路 §6）。 */
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { api } from "@/lib/api";
import { TagChips } from "@/components/tag/TagChips";
import { flowStatusLabel } from "@/lib/flow-labels";
import type { Flow, FlowGraph, FlowMeta } from "@/lib/types";

const FlowCanvasPreview = dynamic(() => import("@/components/flow/FlowCanvasPreview").then((m) => m.FlowCanvasPreview), { ssr: false });

type Props = {
  open: boolean;
  flow: Flow | null;
  flowMeta?: FlowMeta | null;
  publishing?: boolean;
  onClose: () => void;
  onEdit?: () => void;
  onEditMeta?: () => void;
  onPublish?: () => void;
};

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

export function FlowDetailDialog({ open, flow, flowMeta, publishing = false, onClose, onEdit, onEditMeta, onPublish }: Props) {
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
