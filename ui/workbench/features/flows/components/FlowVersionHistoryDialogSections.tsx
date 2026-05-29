"use client";

import dynamic from "next/dynamic";
import { formatVersionTime } from "@/lib/flow-version-history-shared";
import type { FlowVersionHistoryVm } from "@/hooks/use-flow-version-history";

const FlowCanvasPreview = dynamic(() => import("@/components/flow/FlowCanvasPreview").then((m) => m.FlowCanvasPreview), { ssr: false });

export function FlowVersionHistoryFooter({
  vm,
  currentVersion,
  onClose,
}: {
  vm: FlowVersionHistoryVm;
  currentVersion: number;
  onClose: () => void;
}) {
  const { selectedMeta, stats, previewGraph, selected, canRestore, restoring, toggleDiffMode, diffMode, restore } = vm;

  return (
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
        <button type="button" className="btn-outline text-xs" onClick={toggleDiffMode}>
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
  );
}

export function FlowVersionDiffPanel({ vm, currentVersion }: { vm: FlowVersionHistoryVm; currentVersion: number }) {
  const { diffMode, selected, diffTarget, versions, loadDiffGraph, diffResult } = vm;
  if (!diffMode) return null;

  return (
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
  );
}

export function FlowVersionListPanel({ vm, currentVersion }: { vm: FlowVersionHistoryVm; currentVersion: number }) {
  const { versions, loading, selected, setSelected } = vm;

  return (
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
  );
}

export function FlowVersionPreviewPanel({ vm }: { vm: FlowVersionHistoryVm }) {
  const { selectedMeta, previewGraph, previewLoading, stats, versions } = vm;

  return (
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
  );
}
