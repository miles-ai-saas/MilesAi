"use client";

/** 流程版本历史：预览 + 恢复为新版本（链路 §6 Phase 4）。 */
import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { api } from "@/lib/api";
import type { FlowGraph, FlowVersionSummary } from "@/lib/types";

const FlowCanvasPreview = dynamic(() => import("@/components/flow/FlowCanvasPreview").then((m) => m.FlowCanvasPreview), { ssr: false });

interface FlowVersionHistoryDialogProps {
  flowId: string;
  open: boolean;
  currentVersion: number;
  onClose: () => void;
  onRestored: (graph: FlowGraph, newVersion: number) => void;
}

function formatVersionTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("zh-CN", {
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

export function FlowVersionHistoryDialog({ flowId, open, currentVersion, onClose, onRestored }: FlowVersionHistoryDialogProps) {
  const [versions, setVersions] = useState<FlowVersionSummary[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [previewGraph, setPreviewGraph] = useState<FlowGraph | null>(null);
  const [loading, setLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [error, setError] = useState("");
  const [diffMode, setDiffMode] = useState(false);
  const [diffTarget, setDiffTarget] = useState<number | null>(null);
  const [diffGraph, setDiffGraph] = useState<FlowGraph | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);

  const selectedMeta = useMemo(() => versions.find((v) => v.version === selected) ?? null, [versions, selected]);

  const stats = useMemo(() => graphStats(previewGraph), [previewGraph]);

  const loadList = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const list = await api.listFlowVersions(flowId);
      setVersions(list);
      if (list.length > 0) {
        setSelected((prev) => {
          if (prev !== null) return prev;
          const cur = list.find((v) => v.version === currentVersion);
          return cur?.version ?? list[0].version;
        });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载版本失败");
    } finally {
      setLoading(false);
    }
  }, [flowId, currentVersion]);

  useEffect(() => {
    if (open) {
      setSelected(null);
      setPreviewGraph(null);
      void loadList();
    }
  }, [open, loadList]);

  useEffect(() => {
    if (!open || selected === null) return;
    setPreviewLoading(true);
    api
      .getFlowVersion(flowId, selected)
      .then((v) => setPreviewGraph(v.graph_json))
      .catch((e) => {
        setPreviewGraph(null);
        setError(e instanceof Error ? e.message : "加载预览失败");
      })
      .finally(() => setPreviewLoading(false));
  }, [open, flowId, selected]);

  const restore = async () => {
    if (selected === null || !previewGraph) return;
    setRestoring(true);
    setError("");
    try {
      const saved = await api.saveFlowGraph(flowId, previewGraph, `恢复自 v${selected}`);
      onRestored(saved.graph_json, saved.version);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "恢复失败");
    } finally {
      setRestoring(false);
    }
  };

  const canRestore = !restoring && selected !== null && previewGraph !== null && selected !== currentVersion;

  const loadDiffGraph = async (v: number) => {
    setDiffTarget(v);
    setDiffLoading(true);
    try {
      const ver = await api.getFlowVersion(flowId, v);
      setDiffGraph(ver.graph_json);
    } catch (e) {
      setDiffGraph(null);
    } finally {
      setDiffLoading(false);
    }
  };

  const diffResult = useMemo(() => {
    if (!diffMode || !previewGraph || !diffGraph) return null;
    const a = JSON.stringify(previewGraph, null, 2).split("\n");
    const b = JSON.stringify(diffGraph, null, 2).split("\n");
    return { a, b };
  }, [diffMode, previewGraph, diffGraph]);

  return (
    <ResourceDialog
      open={open}
      title="版本历史"
      description="选择历史版本预览画布；「恢复此版本」会另存为新版本号，不会删除旧记录。"
      size="sheet"
      contentMaxWidth="max-w-none"
      onClose={onClose}
      footer={
        <div className="flex w-full flex-wrap items-center justify-between gap-3">
          <div className="min-w-0 text-sm text-ink-muted">
            {selectedMeta ? (
              <>
                <span className="font-medium text-ink">v{selectedMeta.version}</span>
                {selectedMeta.version === currentVersion && <span className="ml-1.5 rounded bg-brand-light px-1.5 py-0.5 text-xs text-brand">当前</span>}
                {previewGraph && (
                  <span className="ml-2 text-xs text-ink-faint">
                    {stats.nodes} 节点 · {stats.edges} 连线
                  </span>
                )}
                {selectedMeta.remark && <span className="mt-0.5 block truncate text-xs">{selectedMeta.remark}</span>}
              </>
            ) : (
              <span className="text-ink-faint">请选择版本</span>
            )}
          </div>
          <div className="flex shrink-0 gap-2">
            <button type="button" className="btn-ghost" onClick={onClose}>
              关闭
            </button>
            <button
              type="button"
              className="btn-outline text-xs"
              onClick={() => {
                if (diffMode) {
                  setDiffMode(false);
                  setDiffTarget(null);
                  setDiffGraph(null);
                } else {
                  setDiffMode(true);
                  setDiffTarget(currentVersion);
                  void loadDiffGraph(currentVersion);
                }
              }}
            >
              {diffMode ? "退出对比" : "对比版本"}
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={!canRestore}
              title={selected === currentVersion ? "已是当前版本，无需恢复" : undefined}
              onClick={() => void restore()}
            >
              {restoring ? "恢复中…" : "恢复此版本"}
            </button>
          </div>
        </div>
      }
    >
      <div className="-mx-2 -mt-2 flex h-[calc(100dvh-14rem-10.5rem)] min-h-[min(420px,60vh)] flex-col overflow-hidden sm:-mx-4">
        {error && <p className="mb-3 shrink-0 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

        {diffMode && (
          <div className="mb-3 shrink-0 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-medium">对比模式</span>
              <span className="text-ink-muted">左侧 v{selected} ↔ 右侧 v</span>
              <select
                className="input-field !w-auto text-xs"
                value={diffTarget ?? ""}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  if (v) void loadDiffGraph(v);
                }}
              >
                {versions.map((v) => (
                  <option key={v.version} value={v.version}>
                    v{v.version} {v.version === currentVersion ? "(当前)" : ""}
                  </option>
                ))}
              </select>
            </div>
            {diffResult && (
              <div className="mt-3 max-h-60 overflow-auto rounded border border-line bg-white p-3 font-mono text-xs">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="mb-1 text-ink-faint">v{selected}</p>
                    {diffResult.a.slice(0, 80).map((line, i) => (
                      <p key={i} className={diffResult.b[i] !== line ? "bg-red-50 text-red-700" : "text-ink-muted"}>
                        {line || " "}
                      </p>
                    ))}
                  </div>
                  <div>
                    <p className="mb-1 text-ink-faint">v{diffTarget}</p>
                    {diffResult.b.slice(0, 80).map((line, i) => (
                      <p key={i} className={diffResult.a[i] !== line ? "bg-green-50 text-green-700" : "text-ink-muted"}>
                        {line || " "}
                      </p>
                    ))}
                  </div>
                </div>
                {diffResult.a.length > 80 && <p className="mt-2 text-ink-faint">... 仅显示前 80 行差异</p>}
              </div>
            )}
          </div>
        )}

        <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-line lg:flex-row">
          <aside className="flex w-full shrink-0 flex-col border-b border-line bg-surface lg:w-64 lg:border-b-0 lg:border-r xl:w-72">
            <div className="flex shrink-0 items-center justify-between border-b border-line px-3 py-2.5">
              <span className="text-xs font-semibold uppercase tracking-wide text-ink-faint">版本列表</span>
              {!loading && versions.length > 0 && (
                <span className="rounded-md bg-surface-muted px-1.5 py-0.5 text-[10px] font-medium text-ink-muted">{versions.length}</span>
              )}
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-2">
              {loading ? (
                <ul className="space-y-2">
                  {[1, 2, 3].map((i) => (
                    <li key={i} className="h-16 animate-pulse rounded-lg bg-surface-muted" />
                  ))}
                </ul>
              ) : versions.length === 0 ? (
                <p className="px-2 py-6 text-center text-sm text-ink-muted">暂无历史版本</p>
              ) : (
                <ul className="space-y-1">
                  {versions.map((v) => {
                    const active = selected === v.version;
                    const isCurrent = v.version === currentVersion;
                    return (
                      <li key={v.id}>
                        <button
                          type="button"
                          onClick={() => setSelected(v.version)}
                          className={`w-full rounded-lg border px-3 py-2.5 text-left transition ${
                            active ? "border-brand bg-brand-light shadow-sm" : "border-transparent hover:border-line hover:bg-surface-muted"
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <span className={`font-semibold tabular-nums ${active ? "text-brand" : "text-ink"}`}>v{v.version}</span>
                            {isCurrent && <span className="rounded bg-brand/15 px-1.5 py-0.5 text-[10px] font-medium text-brand">当前</span>}
                          </div>
                          {v.remark && <p className="mt-1 line-clamp-2 text-xs leading-snug text-ink-muted">{v.remark}</p>}
                          <p className="mt-1 text-[10px] text-ink-faint">{formatVersionTime(v.created_at)}</p>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </aside>

          <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-surface-muted/40">
            <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-line bg-surface px-3 py-2">
              <div className="min-w-0">
                {selectedMeta ? (
                  <>
                    <span className="text-sm font-medium text-ink">预览 v{selectedMeta.version}</span>
                    {previewGraph && !previewLoading && (
                      <span className="ml-2 text-xs text-ink-faint">
                        {stats.nodes} 节点 · {stats.edges} 连线
                      </span>
                    )}
                  </>
                ) : (
                  <span className="text-sm text-ink-muted">画布预览</span>
                )}
              </div>
              {previewLoading && <span className="text-xs text-ink-faint">加载中…</span>}
            </div>
            <div className="relative min-h-0 flex-1">
              {previewLoading ? (
                <div className="flex h-full min-h-[240px] items-center justify-center">
                  <p className="text-sm text-ink-muted">加载预览…</p>
                </div>
              ) : previewGraph ? (
                <FlowCanvasPreview graph={previewGraph} className="absolute inset-0 h-full w-full" />
              ) : (
                <div className="flex h-full min-h-[240px] flex-col items-center justify-center gap-2 px-4 text-center">
                  <p className="text-sm text-ink-muted">{versions.length === 0 ? "保存流程后将在此显示版本" : "在左侧选择版本查看画布"}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </ResourceDialog>
  );
}
