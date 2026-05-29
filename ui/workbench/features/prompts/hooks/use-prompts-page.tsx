"use client";

import { useCallback, useMemo, useState } from "react";
import type { PromptTemplateDialogMode } from "@/features/prompts/components/PromptTemplateDialog";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { usePromptMeta } from "@/features/prompts/hooks/use-prompt-meta";
import { filterBySearch } from "@/lib/filter-search";
import type { PromptTemplate } from "@/lib/types";

function exportPromptTemplate(t: { name: string; content: string; category_id?: string | null; tags?: { id: string }[] }) {
  const pkg = {
    version: "1.0",
    name: t.name,
    content: t.content,
    category_id: t.category_id,
    tag_ids: t.tags?.map((tg) => tg.id) ?? [],
  };
  const blob = new Blob([JSON.stringify(pkg, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${t.name.replace(/[^a-zA-Z0-9\u4e00-\u9fff]/g, "_")}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

export function usePromptsPage() {
  const { ready } = useRequireAuth();
  const promptMeta = usePromptMeta(ready);
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<PromptTemplateDialogMode>("create");
  const [editing, setEditing] = useState<PromptTemplate | null>(null);
  const [tagFilterIds, setTagFilterIds] = useState<string[]>([]);
  const [tagManageOpen, setTagManageOpen] = useState(false);

  const list = usePagedList(
    useCallback((p, s) => api.listPromptTemplates(p, s, undefined, tagFilterIds.length ? tagFilterIds : undefined), [tagFilterIds]),
    { enabled: ready, resetKey: tagFilterIds.join(",") },
  );
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const filtered = useMemo(() => filterBySearch(list.items, search, (t) => `${t.name} ${t.content}`), [list.items, search]);

  const openCreate = () => {
    setEditing(null);
    setDialogMode("create");
    setDialogOpen(true);
  };

  const openView = (t: PromptTemplate) => {
    setEditing(t);
    setDialogMode("view");
    setDialogOpen(true);
  };

  const openEdit = (t: PromptTemplate) => {
    setEditing(t);
    setDialogMode("edit");
    setDialogOpen(true);
  };

  const onDelete = (t: PromptTemplate) => {
    requestConfirm({
      title: "删除模板",
      message: (
        <>
          确定删除模板 <span className="font-medium">{t.name}</span>？
        </>
      ),
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deletePromptTemplate(t.id);
        await list.reload();
      },
    });
  };

  const onExport = (t: PromptTemplate) => {
    exportPromptTemplate(t);
  };

  const onImportFile = async (file: File) => {
    const text = await file.text();
    const pkg = JSON.parse(text);
    const t = pkg.agent || pkg;
    if (!t.name || !t.content) {
      alert("JSON 格式错误：需要 name 和 content 字段");
      return;
    }
    await api.createPromptTemplate(t.name, t.content, t.category_id, t.tag_ids ?? t.tags?.map((tg: { id: string }) => tg.id));
    await list.reload();
  };

  return {
    promptMeta,
    search,
    setSearch,
    list,
    filtered,
    dialogOpen,
    setDialogOpen,
    dialogMode,
    setDialogMode,
    editing,
    tagFilterIds,
    setTagFilterIds,
    tagManageOpen,
    setTagManageOpen,
    confirmDialog,
    openCreate,
    openView,
    openEdit,
    onDelete,
    onExport,
    onImportFile,
  };
}

export type PromptsPageVm = ReturnType<typeof usePromptsPage>;
