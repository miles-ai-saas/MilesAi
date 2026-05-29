"use client";

/** 词库详情与词条（链路 §13）。 */

import { LibraryWordDialog } from "@/features/compliance/components/LibraryWordDialog";
import { ComplianceLibraryBatchImportDialog } from "@/features/compliance/components/ComplianceLibraryBatchImportDialog";
import { ComplianceLibraryWordList } from "@/features/compliance/components/ComplianceLibraryWordList";
import { useComplianceLibraryDetail } from "@/features/compliance/hooks/use-compliance-library-detail";
import type { EnumOption, WordLibrary } from "@/lib/types";

type Props = {
  library: WordLibrary;
  sensitiveActions?: EnumOption[];
  onBack: () => void;
  onLibraryChange: () => void;
};

export function ComplianceLibraryDetail({ library, sensitiveActions = [], onBack, onLibraryChange }: Props) {
  const vm = useComplianceLibraryDetail({ library, onLibraryChange });

  return (
    <div className="col-span-full space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button type="button" className="btn-sm-ghost" onClick={onBack}>
          ← 返回词库列表
        </button>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-sm-outline" onClick={() => vm.setBatchOpen(true)}>
            批量导入
          </button>
          <button type="button" className="btn-sm-primary" onClick={() => vm.openWord("create")}>
            添加词条
          </button>
        </div>
      </div>

      <header className="rounded-xl border border-line bg-surface px-5 py-4 shadow-card">
        <h2 className="text-lg font-semibold text-ink">{library.name}</h2>
        {library.description && <p className="mt-1 text-sm text-ink-muted">{library.description}</p>}
        <div className="mt-2 flex flex-wrap gap-2 text-xs">
          <span className={`rounded-full px-2 py-0.5 ${library.is_active ? "bg-brand-light text-brand" : "bg-surface-muted text-ink-faint"}`}>
            {library.is_active ? "词库已启用" : "词库已停用"}
          </span>
          <span className="text-ink-muted tabular-nums">共 {library.word_count} 条词条</span>
        </div>
      </header>

      <ComplianceLibraryWordList library={library} vm={vm} sensitiveActions={sensitiveActions} />

      <ComplianceLibraryBatchImportDialog
        open={vm.batchOpen}
        libraryName={library.name}
        batchText={vm.batchText}
        onBatchTextChange={vm.setBatchText}
        onClose={() => vm.setBatchOpen(false)}
        onImport={() => void vm.onBatchImport()}
      />

      <LibraryWordDialog
        open={vm.wordDialogOpen}
        mode={vm.wordMode}
        libraryId={library.id}
        word={vm.selectedWord}
        sensitiveActions={sensitiveActions}
        onClose={() => vm.setWordDialogOpen(false)}
        onSaved={() => void vm.onWordSaved()}
        onRequestEdit={vm.wordMode === "view" && vm.selectedWord ? () => vm.openWord("edit", vm.selectedWord) : undefined}
      />
      {vm.confirmDialog}
    </div>
  );
}
