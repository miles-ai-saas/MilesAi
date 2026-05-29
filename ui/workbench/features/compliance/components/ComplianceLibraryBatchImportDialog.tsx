"use client";

import { ResourceDialog } from "@/components/resource/ResourceDialog";

type Props = {
  open: boolean;
  libraryName: string;
  batchText: string;
  onBatchTextChange: (text: string) => void;
  onClose: () => void;
  onImport: () => void;
};

export function ComplianceLibraryBatchImportDialog({ open, libraryName, batchText, onBatchTextChange, onClose, onImport }: Props) {
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
