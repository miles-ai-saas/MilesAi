"use client";

/** 工具工作台（链路 §3 + §4）：目录/调用日志 + `useToolsMeta`。 */

import { TagManageDialog } from "@/components/tag/TagManageDialog";
import { ToolsCatalogTab, ToolsLogsTab, useToolsPage, type ToolsPageVm } from "@/features/tools";
import { ToolCreateDialog } from "@/features/tools/components/ToolCreateDialog";
import { ToolDetailDialog } from "@/features/tools/components/ToolDetailDialog";
import { ToolTestDialog } from "@/features/tools/components/ToolTestDialog";

function ToolsPageOverlays({ vm }: { vm: ToolsPageVm }) {
  return (
    <>
      <ToolCreateDialog
        open={vm.dialogOpen}
        mode={vm.dialogMode}
        kindTabs={vm.kindTabs}
        toolKind={vm.toolKind}
        editing={vm.editing}
        slug={vm.slug}
        name={vm.name}
        description={vm.description}
        tagIds={vm.tagIds}
        version={vm.version}
        requireConfirmation={vm.requireConfirmation}
        parameters={vm.parameters}
        url={vm.url}
        method={vm.method}
        headersJson={vm.headersJson}
        bodyMode={vm.bodyMode}
        timeoutSec={vm.timeoutSec}
        scriptSource={vm.scriptSource}
        busy={vm.busy}
        saveError={vm.saveError}
        onClose={() => vm.setDialogOpen(false)}
        onDismissError={() => vm.setSaveError("")}
        onSubmit={vm.onSave}
        onToolKindChange={vm.setToolKind}
        onSlugChange={vm.setSlug}
        onNameChange={vm.onNameChange}
        onDescriptionChange={vm.setDescription}
        onTagIdsChange={vm.setTagIds}
        onVersionChange={vm.setVersion}
        onRequireConfirmationChange={vm.setRequireConfirmation}
        onParametersChange={vm.setParameters}
        onUrlChange={vm.setUrl}
        onMethodChange={vm.setMethod}
        onHeadersJsonChange={vm.setHeadersJson}
        onBodyModeChange={vm.setBodyMode}
        onTimeoutSecChange={vm.setTimeoutSec}
        onScriptSourceChange={vm.setScriptSource}
      />
      <ToolDetailDialog
        open={vm.detailOpen}
        item={vm.detailTool}
        toolsMeta={vm.toolsMeta}
        onClose={() => vm.setDetailOpen(false)}
        onTest={
          vm.detailTool
            ? () => {
                vm.openTest(vm.detailTool!);
              }
            : undefined
        }
        onEdit={
          vm.detailTool?.source === "custom"
            ? () => {
                vm.setDetailOpen(false);
                void vm.openEdit(vm.detailTool!);
              }
            : undefined
        }
      />
      <ToolTestDialog open={vm.testOpen} tool={vm.testTool} onClose={() => vm.setTestOpen(false)} onRun={vm.runTest} />
      <TagManageDialog open={vm.tagManageOpen} onClose={() => vm.setTagManageOpen(false)} />
      {vm.confirmDialog}
    </>
  );
}

export default function ToolsPage() {
  const vm = useToolsPage();
  const overlays = <ToolsPageOverlays vm={vm} />;

  if (vm.pageTab === "logs") {
    return (
      <>
        <ToolsLogsTab vm={vm} />
        {overlays}
      </>
    );
  }

  return (
    <>
      <ToolsCatalogTab vm={vm} />
      {overlays}
    </>
  );
}
