"use client";

/** 流程调试面板（链路 §6）：KB、query、附图、steps、output。 */
import { useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { formatFlowSteps, type FlowCompileErrorDetail } from "@/lib/flow-run-format";
import { FlowRunArtifactsPreview } from "@/components/flow/FlowRunArtifactsPreview";
import { extractFlowRunArtifacts } from "@/lib/flow-run-artifacts";
import type { KnowledgeBase } from "@/lib/types";

export interface FlowRunState {
  output: string;
  steps: Record<string, unknown>[];
  compileInfo?: string;
  compileErrorDetails?: FlowCompileErrorDetail[];
  error?: string;
}

type ResultTab = "steps" | "output";

export type FlowRunPendingMedia = {
  attachment_id: string;
  filename?: string;
  local_preview: string;
};

interface FlowRunPanelProps {
  kbs: KnowledgeBase[];
  selectedKbIds: string[];
  onKbIdsChange: (ids: string[]) => void;
  query: string;
  onQueryChange: (q: string) => void;
  runState: FlowRunState | null;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
  onSelectCompileNode?: (nodeId: string) => void;
  onRun?: () => void;
  busy?: boolean;
  /** busy 时「运行」按钮文案，如「生视频中…」 */
  runBusyLabel?: string;
  /** 画布含生图/生视频节点时的运行前提示 */
  generativeHint?: string | null;
  /** 异步任务轮询中的说明 */
  generativePollMsg?: string | null;
  generativeProgressPercent?: number | null;
  onCancelGenerativeJobs?: () => void;
  canCancelGenerative?: boolean;
  /** 轮询完成后追加的生成物 */
  extraArtifacts?: import("@/lib/flow-run-artifacts").FlowRunArtifact[];
  pendingMedia?: FlowRunPendingMedia[];
  onPendingMediaChange?: (items: FlowRunPendingMedia[]) => void;
}

export function FlowRunPanel({
  kbs,
  selectedKbIds,
  onKbIdsChange,
  query,
  onQueryChange,
  runState,
  collapsed,
  onToggleCollapsed,
  onSelectCompileNode,
  onRun,
  busy = false,
  runBusyLabel = "运行中…",
  generativeHint = null,
  generativePollMsg = null,
  generativeProgressPercent = null,
  onCancelGenerativeJobs,
  canCancelGenerative = false,
  extraArtifacts = [],
  pendingMedia = [],
  onPendingMediaChange,
}: FlowRunPanelProps) {
  const [tab, setTab] = useState<ResultTab>("output");
  const [uploadingMedia, setUploadingMedia] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const onPickImages = async (files: FileList | null) => {
    if (!files?.length || !onPendingMediaChange || uploadingMedia) return;
    setUploadingMedia(true);
    try {
      const next: FlowRunPendingMedia[] = [];
      for (const file of Array.from(files)) {
        if (!file.type.startsWith("image/")) continue;
        const att = await api.uploadAttachment(file, { purpose: "flow" });
        next.push({
          attachment_id: att.id,
          filename: att.filename,
          local_preview: URL.createObjectURL(file),
        });
      }
      if (next.length) {
        onPendingMediaChange([...pendingMedia, ...next].slice(0, 4));
      }
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "图片上传失败");
    } finally {
      setUploadingMedia(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const removePending = (id: string) => {
    if (!onPendingMediaChange) return;
    const item = pendingMedia.find((p) => p.attachment_id === id);
    if (item?.local_preview) URL.revokeObjectURL(item.local_preview);
    onPendingMediaChange(pendingMedia.filter((p) => p.attachment_id !== id));
  };

  const canRun = Boolean(onRun) && !busy && !uploadingMedia && (query.trim().length > 0 || pendingMedia.length > 0);

  const toggleKb = (id: string) => {
    if (selectedKbIds.includes(id)) {
      onKbIdsChange(selectedKbIds.filter((x) => x !== id));
    } else {
      onKbIdsChange([...selectedKbIds, id]);
    }
  };

  const hasSteps = (runState?.steps?.length ?? 0) > 0;
  const hasOutput = Boolean(runState?.output);
  const hasErrors = (runState?.compileErrorDetails?.length ?? 0) > 0 || Boolean(runState?.error);
  const runArtifacts = useMemo(() => {
    const base = extractFlowRunArtifacts(runState?.steps);
    if (!extraArtifacts.length) return base;
    const seen = new Set(base.map((a) => `${a.kind}:${a.attachmentId}`));
    const merged = [...base];
    for (const item of extraArtifacts) {
      const key = `${item.kind}:${item.attachmentId}`;
      if (!seen.has(key)) {
        seen.add(key);
        merged.push(item);
      }
    }
    return merged;
  }, [runState?.steps, extraArtifacts]);
  const hasArtifacts = runArtifacts.length > 0;

  if (collapsed) {
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

  return (
    <section className="flex max-h-[min(42vh,360px)] min-h-[140px] shrink-0 flex-col border-t border-line bg-surface">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-line px-3 py-2">
        <span className="text-sm font-medium text-ink">调试面板</span>
        <div className="flex items-center gap-2">
          {onRun && (
            <button type="button" className="btn-sm-primary sm:hidden" disabled={!canRun} onClick={onRun}>
              {busy ? runBusyLabel : "运行"}
            </button>
          )}
          {onToggleCollapsed && (
            <button type="button" className="btn-sm-ghost" onClick={onToggleCollapsed}>
              收起
            </button>
          )}
        </div>
      </div>

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
          {pendingMedia.length > 0 && (
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

      {(hasErrors || runState?.compileInfo) && (
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
      )}

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
    </section>
  );
}
