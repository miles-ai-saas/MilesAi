"use client";

import type { FlowRunPanelProps } from "@/features/flows/lib/flow-run-panel-shared";

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
