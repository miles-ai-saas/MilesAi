"use client";

import { useState } from "react";
import { formatFlowSteps } from "@/lib/flow-run-format";
import { extractFlowRunArtifacts } from "@/lib/flow-run-artifacts";
import { FlowRunArtifactsPreview } from "@/components/flow/FlowRunArtifactsPreview";
import { useFlowRunPanelMedia } from "@/hooks/use-flow-run-panel-media";
import type { FlowRunPanelProps } from "@/lib/flow-run-panel-shared";

type ResultTab = "steps" | "output";

export function FlowRunPanelCollapsedBar({
  onToggleCollapsed,
  hasArtifacts,
  hasOutput,
  hasSteps,
}: {
  onToggleCollapsed?: () => void;
  hasArtifacts: boolean;
  hasOutput: boolean;
  hasSteps: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onToggleCollapsed}
      className="flex w-full shrink-0 items-center justify-between border-t border-line bg-surface px-4 py-1.5 text-left text-sm text-ink-muted hover:bg-surface-muted"
    >
      <span>展开调试面板</span>
      <span className="text-xs text-ink-faint">{hasArtifacts ? "有生成物" : hasOutput ? "有输出" : hasSteps ? "有步骤" : "配置 KB 与 query 后运行"}</span>
    </button>
  );
}

export function FlowRunPanelInputs({
  kbs,
  selectedKbIds,
  onKbIdsChange,
  query,
  onQueryChange,
  onRun,
  busy,
  runBusyLabel,
  generativeHint,
  generativePollMsg,
  generativeProgressPercent,
  onCancelGenerativeJobs,
  canCancelGenerative,
  pendingMedia,
  onPendingMediaChange,
  canRun,
}: Pick<
  FlowRunPanelProps,
  | "kbs"
  | "selectedKbIds"
  | "onKbIdsChange"
  | "query"
  | "onQueryChange"
  | "onRun"
  | "busy"
  | "runBusyLabel"
  | "generativeHint"
  | "generativePollMsg"
  | "generativeProgressPercent"
  | "onCancelGenerativeJobs"
  | "canCancelGenerative"
  | "pendingMedia"
  | "onPendingMediaChange"
> & { canRun: boolean }) {
  const { uploadingMedia, fileInputRef, onPickImages, removePending } = useFlowRunPanelMedia(pendingMedia ?? [], onPendingMediaChange);

  const toggleKb = (id: string) => {
    if (selectedKbIds.includes(id)) {
      onKbIdsChange(selectedKbIds.filter((x) => x !== id));
    } else {
      onKbIdsChange([...selectedKbIds, id]);
    }
  };

  return (
    <div className="grid shrink-0 gap-3 border-b border-line px-3 py-3 sm:grid-cols-[1fr_minmax(12rem,20rem)] sm:items-end">
      <div className="min-w-0">
        <p className="mb-1.5 text-xs font-medium text-ink-muted">
          调试知识库
          <span className="ml-1 font-normal text-ink-faint">（未在节点指定 kb_id 时注入）</span>
        </p>
        <div className="flex max-h-24 flex-wrap gap-1.5 overflow-y-auto rounded-lg border border-line bg-surface-muted p-2">
          {kbs.length === 0 ? (
            <span className="text-xs text-ink-faint">暂无知识库</span>
          ) : (
            kbs.map((kb) => {
              const on = selectedKbIds.includes(kb.id);
              return (
                <button
                  key={kb.id}
                  type="button"
                  onClick={() => toggleKb(kb.id)}
                  className={`rounded-md border px-2 py-1 text-xs transition ${
                    on ? "border-brand bg-brand-light text-brand" : "border-line bg-surface text-ink-muted hover:border-brand/40"
                  }`}
                >
                  {kb.name}
                </button>
              );
            })
          )}
        </div>
      </div>
      <div className="min-w-0 space-y-2">
        <label className="block text-xs font-medium text-ink-muted">测试问题 (query)</label>
        {generativeHint && !busy ? (
          <p className="rounded-lg border border-amber-200/80 bg-amber-50/90 px-2.5 py-1.5 text-[11px] leading-relaxed text-amber-900">{generativeHint}</p>
        ) : null}
        {generativeHint && busy ? <p className="text-[11px] leading-relaxed text-amber-800">{runBusyLabel}</p> : null}
        {generativePollMsg ? (
          <div className="rounded-lg border border-amber-200/80 bg-amber-50/90 px-2.5 py-1.5 text-[11px] text-amber-900">
            <div className="flex items-center justify-between gap-2">
              <span>{generativePollMsg}</span>
              {canCancelGenerative && onCancelGenerativeJobs ? (
                <button type="button" className="btn-sm-ghost shrink-0 !px-1.5 text-[10px]" onClick={onCancelGenerativeJobs}>
                  取消
                </button>
              ) : null}
            </div>
            {generativeProgressPercent != null ? (
              <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-amber-200/60">
                <div className="h-full rounded-full bg-amber-600 transition-all" style={{ width: `${generativeProgressPercent}%` }} />
              </div>
            ) : null}
          </div>
        ) : null}
        {pendingMedia && pendingMedia.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {pendingMedia.map((m) => (
              <div key={m.attachment_id} className="relative">
                <img src={m.local_preview} alt={m.filename ?? "附图"} className="h-14 w-14 rounded-lg object-cover ring-1 ring-line" />
                <button
                  type="button"
                  className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-ink text-xs text-surface"
                  aria-label="移除"
                  onClick={() => removePending(m.attachment_id)}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
        <div className="flex gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            className="hidden"
            onChange={(e) => void onPickImages(e.target.files)}
          />
          <button
            type="button"
            className="btn-sm-outline shrink-0"
            disabled={busy || uploadingMedia || !onPendingMediaChange}
            onClick={() => fileInputRef.current?.click()}
          >
            {uploadingMedia ? "上传…" : "图片"}
          </button>
          <input
            className="input-field min-w-0 flex-1"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="输入问题或附图后运行"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && canRun) {
                e.preventDefault();
                onRun?.();
              }
            }}
          />
          {onRun && (
            <button type="button" className="btn-primary hidden shrink-0 sm:inline-flex" disabled={!canRun} onClick={onRun}>
              {busy ? runBusyLabel : "运行"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function FlowRunPanelErrors({
  runState,
  onSelectCompileNode,
}: {
  runState: FlowRunPanelProps["runState"];
  onSelectCompileNode?: (nodeId: string) => void;
}) {
  const hasErrors = (runState?.compileErrorDetails?.length ?? 0) > 0 || Boolean(runState?.error);
  if (!hasErrors && !runState?.compileInfo) return null;

  return (
    <div className="shrink-0 border-b border-line px-3 py-2">
      {runState?.compileErrorDetails && runState.compileErrorDetails.length > 0 ? (
        <ul className="max-h-20 space-y-1 overflow-y-auto text-xs text-red-700">
          {runState.compileErrorDetails.map((e, i) => (
            <li key={`${e.code}-${i}`}>
              {e.node_id && onSelectCompileNode ? (
                <button type="button" className="text-left hover:underline" onClick={() => onSelectCompileNode(e.node_id!)}>
                  [{e.node_id}] {e.message}
                </button>
              ) : (
                <span>
                  {e.node_id ? `[${e.node_id}] ` : ""}
                  {e.message}
                </span>
              )}
            </li>
          ))}
        </ul>
      ) : (
        runState?.compileInfo && <p className="text-xs leading-relaxed text-ink-muted whitespace-pre-wrap">{runState.compileInfo}</p>
      )}
      {runState?.error && <p className="mt-1 text-xs text-red-600">{runState.error}</p>}
    </div>
  );
}

export function FlowRunPanelResults({
  runState,
  runArtifacts,
}: {
  runState: FlowRunPanelProps["runState"];
  runArtifacts: ReturnType<typeof extractFlowRunArtifacts>;
}) {
  const [tab, setTab] = useState<ResultTab>("output");

  const hasSteps = (runState?.steps?.length ?? 0) > 0;
  const hasOutput = Boolean(runState?.output);
  const hasArtifacts = runArtifacts.length > 0;

  return (
    <>
      {hasArtifacts && <FlowRunArtifactsPreview artifacts={runArtifacts} />}
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex shrink-0 gap-1 border-b border-line px-3 pt-2">
          <button
            type="button"
            className={`rounded-t-md px-3 py-1.5 text-xs font-medium ${tab === "output" ? "bg-surface-muted text-brand" : "text-ink-muted hover:text-ink"}`}
            onClick={() => setTab("output")}
          >
            输出
            {(hasOutput || hasArtifacts) && <span className="ml-1 text-ink-faint">●</span>}
          </button>
          <button
            type="button"
            className={`rounded-t-md px-3 py-1.5 text-xs font-medium ${tab === "steps" ? "bg-surface-muted text-brand" : "text-ink-muted hover:text-ink"}`}
            onClick={() => setTab("steps")}
          >
            执行步骤
            {hasSteps && <span className="ml-1 text-ink-faint">●</span>}
          </button>
        </div>
        <pre className="min-h-[80px] flex-1 overflow-auto bg-surface-muted px-3 py-2 font-mono text-[11px] leading-relaxed text-ink">
          {tab === "output" ? runState?.output || "运行后展示最终输出" : runState?.steps?.length ? formatFlowSteps(runState.steps) : "运行后展示逐步 steps"}
        </pre>
      </div>
    </>
  );
}
