"use client";

import { useCallback, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { filterBySearch } from "@/lib/filter-search";
import { TagChips } from "@/components/tag/TagChips";
import { TagFilterSelect } from "@/components/tag/TagFilterSelect";
import { TagManageDialog } from "@/components/tag/TagManageDialog";
import { TagPicker } from "@/components/tag/TagPicker";
import type { PromptTemplate } from "@/lib/types";

export default function PromptsPage() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<PromptTemplate | null>(null);
  const [name, setName] = useState("");
  const [content, setContent] = useState("你是企业智能助手，请准确、简洁地回答用户问题。");
  const [tagIds, setTagIds] = useState<string[]>([]);
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
    setName("");
    setContent("你是企业智能助手，请准确、简洁地回答用户问题。");
    setTagIds([]);
    setDialogOpen(true);
  };

  const openEdit = (t: PromptTemplate) => {
    setEditing(t);
    setName(t.name);
    setContent(t.content);
    setTagIds((t.tags ?? []).map((x) => x.id));
    setDialogOpen(true);
  };

  const onSave = async () => {
    if (!name.trim()) return;
    if (editing) {
      await api.updatePromptTemplate(editing.id, {
        name: name.trim(),
        content,
        category_id: null,
        tag_ids: tagIds,
      });
    } else {
      await api.createPromptTemplate(name.trim(), content, undefined, undefined, tagIds);
    }
    setDialogOpen(false);
    await list.reload();
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
        description="管理系统提示词模板，供智能体与流程编排复用；支持按名称或正文搜索。"
        searchPlaceholder="搜索模板名称或内容"
        search={search}
        onSearchChange={setSearch}
        headerAction={
          <div className="flex flex-wrap items-center gap-2">
            <TagFilterSelect value={tagFilterIds} onChange={setTagFilterIds} />
            <button
              type="button"
              className="btn-ghost border border-line text-sm"
              onClick={() => setTagManageOpen(true)}
            >
              管理标签
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
        <AddResourceCard label="添加新模板" hint="创建可复用的系统提示词" onClick={openCreate} />
        {filtered.map((t) => (
          <ResourceItemCard
            key={t.id}
            title={t.name}
            description={t.content}
            badge={t.is_active ? "启用" : "停用"}
            meta={<TagChips tags={t.tags} />}
            actions={<CardActions onEdit={() => openEdit(t)} onDelete={() => onDelete(t)} />}
          />
        ))}
      </ResourceListLayout>

      <ResourceDialog
        open={dialogOpen}
        title={editing ? "编辑提示词模板" : "新建提示词模板"}
        onClose={() => setDialogOpen(false)}
        footer={
          <>
            <button type="button" className="btn-ghost" onClick={() => setDialogOpen(false)}>
              取消
            </button>
            <button type="button" className="btn-primary" onClick={onSave}>
              保存
            </button>
          </>
        }
      >
        <label className="block text-sm">
          <span className="mb-1 block text-ink-muted">标签</span>
          <TagPicker value={tagIds} onChange={setTagIds} />
        </label>
        <input
          className="input-field w-full"
          placeholder="模板名称"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <textarea
          className="input-field h-32 w-full font-mono text-sm"
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
      </ResourceDialog>
      <TagManageDialog open={tagManageOpen} onClose={() => setTagManageOpen(false)} />
      {confirmDialog}
    </>
  );
}
