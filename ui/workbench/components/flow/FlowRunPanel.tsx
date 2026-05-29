"use client";

import { useMemo } from "react";
import { extractFlowRunArtifacts } from "@/lib/flow-run-artifacts";
import {
  FlowRunPanelCollapsedBar,
  FlowRunPanelErrors,
  FlowRunPanelInputs,
  FlowRunPanelResults,
} from "@/components/flow/FlowRunPanelSections";
import { useFlowRunPanelMedia } from "@/hooks/use-flow-run-panel-media";
import type { FlowRunPanelProps, FlowRunState, FlowRunPendingMedia } from "@/lib/flow-run-panel-shared";

export type { FlowRunState, FlowRunPendingMedia };

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
  const { uploadingMedia } = useFlowRunPanelMedia(pendingMedia, onPendingMediaChange);

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

  const hasSteps = (runState?.steps?.length ?? 0) > 0;
  const hasOutput = Boolean(runState?.output);
  const hasArtifacts = runArtifacts.length > 0;

  const canRun = Boolean(onRun) && !busy && !uploadingMedia && (query.trim().length > 0 || pendingMedia.length > 0);

  if (collapsed) {
    return (
      <FlowRunPanelCollapsedBar
        onToggleCollapsed={onToggleCollapsed}
        hasArtifacts={hasArtifacts}
        hasOutput={hasOutput}
        hasSteps={hasSteps}
      />
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

      <FlowRunPanelInputs
        kbs={kbs}
        selectedKbIds={selectedKbIds}
        onKbIdsChange={onKbIdsChange}
        query={query}
        onQueryChange={onQueryChange}
        onRun={onRun}
        busy={busy}
        runBusyLabel={runBusyLabel}
        generativeHint={generativeHint}
        generativePollMsg={generativePollMsg}
        generativeProgressPercent={generativeProgressPercent}
        onCancelGenerativeJobs={onCancelGenerativeJobs}
        canCancelGenerative={canCancelGenerative}
        pendingMedia={pendingMedia}
        onPendingMediaChange={onPendingMediaChange}
        canRun={canRun}
      />

      <FlowRunPanelErrors runState={runState} onSelectCompileNode={onSelectCompileNode} />

      <FlowRunPanelResults runState={runState} runArtifacts={runArtifacts} />
    </section>
  );
}
