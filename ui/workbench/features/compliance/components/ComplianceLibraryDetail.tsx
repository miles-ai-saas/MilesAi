"use client";

/** 词库详情与词条（链路 §13）。 */

import { useCallback, useState } from "react";
import { LibraryWordDialog } from "@/components/compliance/LibraryWordDialog";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { api } from "@/lib/api";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { sensitiveActionLabel } from "@/lib/compliance-labels";
import type { EnumOption, LibraryWord, WordLibrary } from "@/lib/types";

type Props = {
  library: WordLibrary;
  sensitiveActions?: EnumOption[];
  onBack: () => void;
  onLibraryChange: () => void;
};

export function ComplianceLibraryDetail({ library, sensitiveActions = [], onBack, onLibraryChange }: Props) {
  const [batchOpen, setBatchOpen] = useState(false);
  const [batchText, setBatchText] = useState("");
  const [wordDialogOpen, setWordDialogOpen] = useState(false);
  const [wordMode, setWordMode] = useState<"create" | "view" | "edit">("create");
  const [selectedWord, setSelectedWord] = useState<LibraryWord | null>(null);

  const words = usePagedList(
    useCallback((p, s) => api.listLibraryWords(library.id, p, s), [library.id]),
    { resetKey: library.id },
  );
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const openWord = (mode: "create" | "view" | "edit", word: LibraryWord | null = null) => {
    setWordMode(mode);
    setSelectedWord(word);
    setWordDialogOpen(true);
  };

  const onBatchImport = async () => {
    const lines = batchText
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    if (!lines.length) return;
    const batch = lines.map((line) => {
      const [w, act] = line.split(",").map((s) => s.trim());
      return {
        word: w,
        action: (act === "warn" ? "warn" : "block") as "warn" | "block",
      };
    });
    await api.batchAddLibraryWords(library.id, batch);
    setBatchText("");
    setBatchOpen(false);
    await words.reload();
    onLibraryChange();
  };

  const onDeleteWord = (w: LibraryWord) => {
    requestConfirm({
      title: "从词库移除",
      message: (
        <>
          确定从「{library.name}」移除词条 <span className="font-medium">{w.word}</span>？
          <span className="mt-1 block text-xs text-ink-muted">不会删除其他词库中的同一词面。</span>
        </>
      ),
      destructive: true,
      confirmLabel: "移除",
      onConfirm: async () => {
        await api.deleteLibraryWord(library.id, w.id);
        await words.reload();
        onLibraryChange();
      },
    });
  };

  return (
    <div className="col-span-full space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button type="button" className="btn-sm-ghost" onClick={onBack}>
          ← 返回词库列表
        </button>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-sm-outline" onClick={() => setBatchOpen(true)}>
            批量导入
          </button>
          <button type="button" className="btn-sm-primary" onClick={() => openWord("create")}>
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
          words.items.map((w) => (
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
                      onClick: async () => {
                        await api.updateLibraryWord(library.id, w.id, {
                          is_active: !w.is_active,
                        });
                        await words.reload();
                      },
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

      <ResourceDialog
        open={batchOpen}
        title={`批量导入 · ${library.name}`}
        onClose={() => setBatchOpen(false)}
        footer={
          <>
            <button type="button" className="btn-ghost" onClick={() => setBatchOpen(false)}>
              取消
            </button>
            <button type="button" className="btn-primary" onClick={() => void onBatchImport()}>
              导入
            </button>
          </>
        }
      >
        <p className="text-xs text-ink-muted">
          每行一条：<span className="font-mono">词语</span> 或 <span className="font-mono">词语,block</span> / <span className="font-mono">词语,warn</span>{" "}
          或上传 CSV 文件
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
                  setBatchText((prev) => (prev ? prev + "\n" + text : text));
                };
                reader.readAsText(file);
              }}
            />
          </label>
          {batchText && (
            <button type="button" className="btn-sm-ghost text-xs" onClick={() => setBatchText("")}>
              清空
            </button>
          )}
        </div>
        <textarea
          className="input-field mt-2 min-h-[140px] w-full font-mono text-xs"
          value={batchText}
          onChange={(e) => setBatchText(e.target.value)}
          placeholder={"违禁品,block\n内部资料,warn"}
        />
      </ResourceDialog>

      <LibraryWordDialog
        open={wordDialogOpen}
        mode={wordMode}
        libraryId={library.id}
        word={selectedWord}
        sensitiveActions={sensitiveActions}
        onClose={() => setWordDialogOpen(false)}
        onSaved={async () => {
          await words.reload();
          onLibraryChange();
        }}
        onRequestEdit={wordMode === "view" && selectedWord ? () => openWord("edit", selectedWord) : undefined}
      />
      {confirmDialog}
    </div>
  );
}
