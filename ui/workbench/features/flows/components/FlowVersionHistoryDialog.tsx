"use client";

/** 流程版本历史：预览 + 恢复为新版本（链路 §6 Phase 4）。 */

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import {
  FlowVersionDiffPanel,
  FlowVersionHistoryFooter,
  FlowVersionListPanel,
  FlowVersionPreviewPanel,
} from "@/features/flows/components/FlowVersionHistoryDialogSections";
import { useFlowVersionHistory, type FlowVersionHistoryProps } from "@/features/flows/hooks/use-flow-version-history";

export function FlowVersionHistoryDialog(props: FlowVersionHistoryProps) {
  const vm = useFlowVersionHistory(props);

  return (
    <ResourceDialog
      open={props.open}
      title="版本历史"
      description="选择历史版本预览画布；「恢复此版本」会另存为新版本号，不会删除旧记录。"
      size="sheet"
      contentMaxWidth="max-w-none"
      onClose={props.onClose}
      footer={<FlowVersionHistoryFooter vm={vm} currentVersion={props.currentVersion} onClose={props.onClose} />}
    >
      <div className="-mx-2 -mt-2 flex h-[calc(100dvh-14rem-10.5rem)] min-h-[min(420px,60vh)] flex-col overflow-hidden sm:-mx-4">
        {vm.error && <p className="mb-3 shrink-0 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{vm.error}</p>}

        <FlowVersionDiffPanel vm={vm} currentVersion={props.currentVersion} />

        <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-line lg:flex-row">
          <FlowVersionListPanel vm={vm} currentVersion={props.currentVersion} />
          <FlowVersionPreviewPanel vm={vm} />
        </div>
      </div>
    </ResourceDialog>
  );
}
