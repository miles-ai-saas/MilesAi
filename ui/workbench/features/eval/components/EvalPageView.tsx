"use client";

import { EvalCasesDialog } from "@/features/eval/components/EvalCasesDialog";
import { EvalDatasetDialog } from "@/features/eval/components/EvalDatasetDialog";
import { EvalDatasetsTab } from "@/features/eval/components/EvalDatasetsTab";
import { EvalPageLayout } from "@/features/eval/components/EvalPageLayout";
import { EvalRunCreateDialog } from "@/features/eval/components/EvalRunCreateDialog";
import { EvalRunDetailTab } from "@/features/eval/components/EvalRunDetailTab";
import { EvalRunsTab } from "@/features/eval/components/EvalRunsTab";
import type { EvalPageVm } from "@/features/eval/hooks/use-eval-page";

export function EvalPageView({ vm }: { vm: EvalPageVm }) {
  return (
    <>
      <EvalPageLayout vm={vm}>
        {vm.actionMsg ? (
          <p className="mb-4 text-sm text-ink-muted" role="status">
            {vm.actionMsg}
          </p>
        ) : null}
        {vm.tab === "datasets" ? <EvalDatasetsTab vm={vm} /> : null}
        {vm.tab === "runs" ? <EvalRunsTab vm={vm} /> : null}
        {vm.tab === "run_detail" ? <EvalRunDetailTab vm={vm} /> : null}
      </EvalPageLayout>

      <EvalDatasetDialog
        open={vm.datasetDialogOpen}
        dataset={vm.editingDataset}
        onClose={() => vm.setDatasetDialogOpen(false)}
        onSaved={vm.reloadDatasets}
      />

      <EvalCasesDialog
        open={vm.casesDialogOpen}
        dataset={vm.casesDataset}
        onClose={() => vm.setCasesDialogOpen(false)}
        onChanged={vm.reloadDatasets}
      />

      <EvalRunCreateDialog
        open={vm.runCreateOpen}
        datasets={vm.datasetsList.items}
        onClose={() => vm.setRunCreateOpen(false)}
        onCreate={vm.onCreateRun}
      />

      {vm.confirmDialog}
    </>
  );
}
