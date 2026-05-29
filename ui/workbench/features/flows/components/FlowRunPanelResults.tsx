"use client";

import { useState } from "react";
import { FlowRunArtifactsPreview } from "@/features/flows/components/FlowRunArtifactsPreview";
import { formatFlowSteps } from "@/features/flows/lib/flow-run-format";
import { extractFlowRunArtifacts } from "@/features/flows/lib/flow-run-artifacts";
import type { FlowRunPanelProps } from "@/features/flows/lib/flow-run-panel-shared";

type ResultTab = "steps" | "output";

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
