"use client";

/** 流程画布编辑（链路 §6）：graph、属性面板、调试运行。 */

import dynamic from "next/dynamic";
import { FlowEditHeader } from "@/components/flow/FlowEditHeader";
import { FlowMetaDialog } from "@/components/flow/FlowMetaDialog";
import { FlowRunPanel } from "@/components/flow/FlowRunPanel";
import { FlowVersionHistoryDialog } from "@/components/flow/FlowVersionHistoryDialog";
import { useFlowEditPage } from "@/hooks/use-flow-edit-page";

const FlowCanvas = dynamic(() => import("@/components/flow/FlowCanvas").then((m) => m.FlowCanvas), { ssr: false });

export default function FlowEditPage() {
  const vm = useFlowEditPage();

  return (
    <div ref={vm.shellRef} className={`flex h-full min-h-0 w-full flex-1 flex-col overflow-hidden bg-surface ${vm.isFullscreen ? "max-h-[100dvh]" : ""}`}>
      <FlowEditHeader
        flowName={vm.flowName}
        flowDescription={vm.flowDescription}
        flowId={vm.id}
        currentVersion={vm.currentVersion}
        busy={vm.busy}
        msg={vm.msg}
        isFullscreen={vm.isFullscreen}
        onToggleFullscreen={() => void vm.toggleFullscreen()}
        onEditMeta={() => vm.setMetaOpen(true)}
        onSave={() => void vm.save()}
        onPublish={() => void vm.publish()}
        onHistory={() => vm.setHistoryOpen(true)}
        onCompile={() => void vm.checkCompile()}
        onRun={() => void vm.runTest()}
        runBusyLabel={vm.generativeRun.busyRunLabel}
      />

      <FlowMetaDialog
        open={vm.metaOpen}
        initialName={vm.flowName}
        initialDescription={vm.flowDescription}
        initialTagIds={vm.flowTagIds}
        busy={vm.busy}
        onClose={() => vm.setMetaOpen(false)}
        onSave={vm.saveFlowMeta}
      />

      <div className="relative min-h-0 flex-1 bg-surface-muted">
        {vm.initialGraph === undefined ? (
          <div className="flex h-full items-center justify-center text-sm text-ink-muted">加载画布…</div>
        ) : (
          <FlowCanvas
            canvasRef={vm.canvasRef}
            initialGraph={vm.initialGraph}
            onGraphChange={vm.onGraphChange}
            currentFlowId={vm.id}
            kbs={vm.kbs}
            models={vm.models}
            prompts={vm.prompts}
            toolCatalog={vm.toolCatalog}
            className="h-full"
          />
        )}
      </div>

      <FlowRunPanel
        kbs={vm.kbs}
        selectedKbIds={vm.selectedKbIds}
        onKbIdsChange={vm.setSelectedKbIds}
        query={vm.testQuery}
        onQueryChange={vm.setTestQuery}
        runState={vm.runState}
        busy={vm.busy}
        pendingMedia={vm.runMedia}
        onPendingMediaChange={vm.setRunMedia}
        collapsed={!vm.debugPanelOpen}
        onToggleCollapsed={() => vm.setDebugPanelOpen((v) => !v)}
        onSelectCompileNode={(nodeId) => vm.canvasRef.current?.selectNode(nodeId)}
        onRun={() => void vm.runTest()}
        runBusyLabel={vm.generativeRun.busyRunLabel}
        generativeHint={vm.generativeRun.preRunMessage}
        generativePollMsg={vm.generativePollMsg}
        generativeProgressPercent={vm.generativeProgress}
        canCancelGenerative={vm.canCancelGenerative}
        onCancelGenerativeJobs={vm.cancelGenerativeJobs}
        extraArtifacts={vm.extraRunArtifacts}
      />

      <FlowVersionHistoryDialog
        flowId={vm.id}
        open={vm.historyOpen}
        currentVersion={vm.currentVersion}
        onClose={() => vm.setHistoryOpen(false)}
        onRestored={vm.restoreVersion}
      />
    </div>
  );
}
