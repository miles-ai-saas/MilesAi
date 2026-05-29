"use client";

/** 词库详情与词条（链路 §13）。 */

import { CardActions } from "@/components/resource/CardActions";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { LibraryWordDialog } from "@/features/compliance/components/LibraryWordDialog";
import { useComplianceLibraryDetail } from "@/features/compliance/hooks/use-compliance-library-detail";
import { sensitiveActionLabel } from "@/features/compliance/lib/compliance-labels";
import type { EnumOption, LibraryWord, WordLibrary } from "@/lib/types";

type Props = {
  library: WordLibrary;
  sensitiveActions?: EnumOption[];
  onBack: () => void;
  onLibraryChange: () => void;
};

function ComplianceLibraryBatchImportDialog({
  open,
  libraryName,
  batchText,
  onBatchTextChange,
  onClose,
  onImport,
}: {
  open: boolean;
  libraryName: string;
  batchText: string;
  onBatchTextChange: (text: string) => void;
  onClose: () => void;
  onImport: () => void;
}) {
  return (
    <ResourceDialog
      open={open}
      title={`批量导入 · ${libraryName}`}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={onClose}>
            取消
          </button>
          <button type="button" className="btn-primary" onClick={onImport}>
            导入
          </button>
        </>
      }
    >
      <p className="text-xs text-ink-muted">
        每行一条：<span className="font-mono">词语</span> 或 <span className="font-mono">词语,block</span> / <span className="font-mono">词语,warn</span> 或上传 CSV 文件
      </p>
      <div className="mt-2 flex items-center gap-2">
        <label className="btn-sm-outline cursor-pointer">
          上传 CSV
          <input
            type="file"
            accept=".csv,.txt"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              const reader = new FileReader();
              reader.onload = () => {
                const text = reader.result as string;
                onBatchTextChange(batchText ? batchText + "\n" + text : text);
              };
              reader.readAsText(file);
            }}
          />
        </label>
        {batchText ? (
          <button type="button" className="btn-sm-ghost text-xs" onClick={() => onBatchTextChange("")}>
            清空
          </button>
        ) : null}
      </div>
      <textarea
        className="input-field mt-2 min-h-[140px] w-full font-mono text-xs"
        value={batchText}
        onChange={(e) => onBatchTextChange(e.target.value)}
        placeholder={"违禁品,block\n内部资料,warn"}
      />
    </ResourceDialog>
  );
}

export function ComplianceLibraryDetail({ library, sensitiveActions = [], onBack, onLibraryChange }: Props) {
  const vm = useComplianceLibraryDetail({ library, onLibraryChange });
  const { words, openWord, onDeleteWord, toggleWordActive } = vm;

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

      <div className="resource-card-grid">
        {words.loading && words.items.length === 0 ? (
          <p className="col-span-full py-8 text-center text-sm text-ink-muted">加载词条…</p>
        ) : words.items.length === 0 ? (
          <p className="col-span-full rounded-xl border border-dashed border-line py-12 text-center text-sm text-ink-faint">
            本词库暂无词条，点击「添加词条」或「批量导入」
          </p>
        ) : (
          words.items.map((w: LibraryWord) => (
            <ResourceItemCard
              key={w.id}
              title={w.word}
              description={sensitiveActions.find((o) => o.value === w.action)?.hint ?? (w.action === "block" ? "命中后拦截请求" : "命中后记录警告日志")}
              badge={sensitiveActionLabel(w.action, null, sensitiveActions)}
              muted={!w.is_active}
              meta={<span>{w.is_active ? "已启用" : "本库内停用"}</span>}
              actions={
                <CardActions
                  onView={() => openWord("view", w)}
                  onEdit={() => openWord("edit", w)}
                  onDelete={() => onDeleteWord(w)}
                  actions={[
                    {
                      label: w.is_active ? "停用" : "启用",
                      onClick: () => void toggleWordActive(w),
                    },
                  ]}
                />
              }
            />
          ))
        )}
      </div>

      {!words.loading && words.items.length > 0 && (
        <ResourceListFooter
          page={words.page}
          size={words.size}
          total={words.total}
          onPageChange={words.setPage}
          onSizeChange={words.setSize}
          className="col-span-full"
        />
      )}

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
