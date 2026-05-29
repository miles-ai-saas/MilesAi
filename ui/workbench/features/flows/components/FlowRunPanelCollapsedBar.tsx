"use client";

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
