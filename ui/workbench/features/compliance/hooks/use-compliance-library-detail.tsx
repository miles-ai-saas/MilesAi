"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import type { LibraryWord, WordLibrary } from "@/lib/types";

type Params = {
  library: WordLibrary;
  onLibraryChange: () => void;
};

export function useComplianceLibraryDetail({ library, onLibraryChange }: Params) {
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

  const toggleWordActive = async (w: LibraryWord) => {
    await api.updateLibraryWord(library.id, w.id, { is_active: !w.is_active });
    await words.reload();
  };

  const onWordSaved = async () => {
    await words.reload();
    onLibraryChange();
  };

  return {
    words,
    batchOpen,
    setBatchOpen,
    batchText,
    setBatchText,
    wordDialogOpen,
    setWordDialogOpen,
    wordMode,
    selectedWord,
    openWord,
    onBatchImport,
    onDeleteWord,
    toggleWordActive,
    onWordSaved,
    confirmDialog,
  };
}

export type ComplianceLibraryDetailVm = ReturnType<typeof useComplianceLibraryDetail>;
