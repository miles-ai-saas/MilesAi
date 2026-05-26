"use client";

import { useCallback, useMemo, useState } from "react";
import { PromptTemplateDialog } from "@/components/prompt/PromptTemplateDialog";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { filterBySearch } from "@/lib/filter-search";
import { TagChips } from "@/components/tag/TagChips";
import { TagFilterSelect } from "@/components/tag/TagFilterSelect";
import { TagManageDialog } from "@/components/tag/TagManageDialog";
import type { PromptTemplate } from "@/lib/types";

function contentPreview(text: string, max = 120): string {
  const t = text.trim().replace(/\s+/g, " ");
  if (!t) return "（空正文）";
  if (t.length <= max) return t;
  return `${t.slice(0, max)}…`;
}

export default function PromptsPage() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<PromptTemplate | null>(null);
  const [tagFilterIds, setTagFilterIds] = useState<string[]>([]);
  const [tagManageOpen, setTagManageOpen] = useState(false);

  const list = usePagedList(
    useCallback(
      (p, s) =>
        api.listPromptTemplates(p, s, undefined, tagFilterIds.length ? tagFilterIds : undefined),
      [tagFilterIds],
    ),
    { enabled: ready, resetKey: tagFilterIds.join(",") },
  );
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (t) => `${t.name} ${t.content}`),
    [list.items, search],
  );

  const openCreate = () => {
    setEditing(null);
    setDialogOpen(true);
  };

  const openEdit = (t: PromptTemplate) => {
    setEditing(t);
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

  return (
    <>
      <ResourceListLayout
        title="提示词模板"
        description="管理系统提示词（Markdown），供智能体 system prompt 与流程编排复用；支持按名称、正文或标签筛选。"
        searchPlaceholder="搜索模板名称或内容"
        search={search}
        onSearchChange={setSearch}
        headerAction={
          <div className="flex flex-wrap items-center gap-2">
            <TagFilterSelect value={tagFilterIds} onChange={setTagFilterIds} />
            <button
              type="button"
              className="btn-sm-outline"
              onClick={() => setTagManageOpen(true)}
            >
              管理标签
            </button>
            <button type="button" className="btn-sm-primary" onClick={openCreate}>
              新建模板
            </button>
          </div>
        }
        loading={list.loading}
        footer={
          !list.loading ? (
            <ResourceListFooter
              page={list.page}
              size={list.size}
              total={list.total}
              onPageChange={list.setPage}
            />
          ) : null
        }
      >
        <AddResourceCard label="新建提示词模板" hint="Markdown 正文 · 编辑 / 预览" onClick={openCreate} />
        {filtered.map((t) => (
          <ResourceItemCard
            key={t.id}
            title={t.name}
            description={contentPreview(t.content)}
            badge={t.is_active ? "启用" : "停用"}
            meta={
              <div className="space-y-2">
                <span className="inline-block rounded border border-line px-1.5 py-px text-[10px] text-ink-faint">
                  Markdown
                </span>
                <TagChips tags={t.tags} />
              </div>
            }
            actions={<CardActions onEdit={() => openEdit(t)} onDelete={() => onDelete(t)} />}
          />
        ))}
      </ResourceListLayout>

      <PromptTemplateDialog
        open={dialogOpen}
        template={editing}
        onClose={() => setDialogOpen(false)}
        onSaved={() => list.reload()}
      />
      <TagManageDialog open={tagManageOpen} onClose={() => setTagManageOpen(false)} />
      {confirmDialog}
    </>
  );
}
