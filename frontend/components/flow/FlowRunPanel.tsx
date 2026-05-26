"use client";

/** 流程调试面板（链路 §6）：KB、query、steps、output。 */
import { useState } from "react";
import {
  formatFlowSteps,
  type FlowCompileErrorDetail,
} from "@/components/flow/FlowNodeInspector";
import type { KnowledgeBase } from "@/lib/types";

export interface FlowRunState {
  output: string;
  steps: Record<string, unknown>[];
  compileInfo?: string;
  compileErrorDetails?: FlowCompileErrorDetail[];
  error?: string;
}

type ResultTab = "steps" | "output";

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
  busy,
}: FlowRunPanelProps) {
  const [tab, setTab] = useState<ResultTab>("output");

  const toggleKb = (id: string) => {
    if (selectedKbIds.includes(id)) {
      onKbIdsChange(selectedKbIds.filter((x) => x !== id));
    } else {
      onKbIdsChange([...selectedKbIds, id]);
    }
  };

  const hasSteps = (runState?.steps?.length ?? 0) > 0;
  const hasOutput = Boolean(runState?.output);
  const hasErrors =
    (runState?.compileErrorDetails?.length ?? 0) > 0 || Boolean(runState?.error);

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={onToggleCollapsed}
        className="flex w-full shrink-0 items-center justify-between border-t border-line bg-surface px-4 py-1.5 text-left text-sm text-ink-muted hover:bg-surface-muted"
      >
        <span>展开调试面板</span>
        <span className="text-xs text-ink-faint">
          {hasOutput ? "有输出" : hasSteps ? "有步骤" : "配置 KB 与 query 后运行"}
        </span>
      </button>
    );
  }

  return (
    <section className="flex max-h-[min(42vh,360px)] min-h-[140px] shrink-0 flex-col border-t border-line bg-surface">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-line px-3 py-2">
        <span className="text-sm font-medium text-ink">调试面板</span>
        <div className="flex items-center gap-2">
          {onRun && (
            <button
              type="button"
              className="btn-sm-primary sm:hidden"
              disabled={busy}
              onClick={onRun}
            >
              运行
            </button>
          )}
          {onToggleCollapsed && (
            <button
              type="button"
              className="btn-sm-ghost"
              onClick={onToggleCollapsed}
            >
              收起
            </button>
          )}
        </div>
      </div>

      <div className="grid shrink-0 gap-3 border-b border-line px-3 py-3 sm:grid-cols-[1fr_minmax(12rem,20rem)] sm:items-end">
        <div className="min-w-0">
          <p className="mb-1.5 text-xs font-medium text-ink-muted">
            调试知识库
            <span className="ml-1 font-normal text-ink-faint">
              （未在节点指定 kb_id 时注入）
            </span>
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
                      on
                        ? "border-brand bg-brand-light text-brand"
                        : "border-line bg-surface text-ink-muted hover:border-brand/40"
                    }`}
                  >
                    {kb.name}
                  </button>
                );
              })
            )}
          </div>
        </div>
        <div className="min-w-0">
          <label className="mb-1.5 block text-xs font-medium text-ink-muted">
            测试问题 (query)
          </label>
          <div className="flex gap-2">
            <input
              className="input-field min-w-0 flex-1"
              value={query}
              onChange={(e) => onQueryChange(e.target.value)}
              placeholder="输入用户问题"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && onRun) {
                  e.preventDefault();
                  onRun();
                }
              }}
            />
            {onRun && (
              <button
                type="button"
                className="btn-primary hidden shrink-0 sm:inline-flex"
                disabled={busy}
                onClick={onRun}
              >
                运行
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
                    <button
                      type="button"
                      className="text-left hover:underline"
                      onClick={() => onSelectCompileNode(e.node_id!)}
                    >
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
            runState?.compileInfo && (
              <p className="text-xs leading-relaxed text-ink-muted whitespace-pre-wrap">
                {runState.compileInfo}
              </p>
            )
          )}
          {runState?.error && (
            <p className="mt-1 text-xs text-red-600">{runState.error}</p>
          )}
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex shrink-0 gap-1 border-b border-line px-3 pt-2">
          <button
            type="button"
            className={`rounded-t-md px-3 py-1.5 text-xs font-medium ${
              tab === "output"
                ? "bg-surface-muted text-brand"
                : "text-ink-muted hover:text-ink"
            }`}
            onClick={() => setTab("output")}
          >
            输出
            {hasOutput && <span className="ml-1 text-ink-faint">●</span>}
          </button>
          <button
            type="button"
            className={`rounded-t-md px-3 py-1.5 text-xs font-medium ${
              tab === "steps"
                ? "bg-surface-muted text-brand"
                : "text-ink-muted hover:text-ink"
            }`}
            onClick={() => setTab("steps")}
          >
            执行步骤
            {hasSteps && <span className="ml-1 text-ink-faint">●</span>}
          </button>
        </div>
        <pre className="min-h-[80px] flex-1 overflow-auto bg-surface-muted px-3 py-2 font-mono text-[11px] leading-relaxed text-ink">
          {tab === "output"
            ? runState?.output || "运行后展示最终输出"
            : runState?.steps?.length
              ? formatFlowSteps(runState.steps)
              : "运行后展示逐步 steps"}
        </pre>
      </div>
    </section>
  );
}
