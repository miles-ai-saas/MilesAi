"use client";

import { useCallback, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { filterBySearch } from "@/lib/filter-search";
import type { PromptTemplate } from "@/lib/types";

export default function PromptsPage() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<PromptTemplate | null>(null);
  const [name, setName] = useState("");
  const [content, setContent] = useState("你是企业智能助手，请准确、简洁地回答用户问题。");

  const list = usePagedList(useCallback((p, s) => api.listPromptTemplates(p, s), []), {
    enabled: ready,
  });

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (t) => `${t.name} ${t.content}`),
    [list.items, search],
  );

  const openCreate = () => {
    setEditing(null);
    setName("");
    setContent("你是企业智能助手，请准确、简洁地回答用户问题。");
    setDialogOpen(true);
  };

  const openEdit = (t: PromptTemplate) => {
    setEditing(t);
    setName(t.name);
    setContent(t.content);
    setDialogOpen(true);
  };

  const onSave = async () => {
    if (!name.trim()) return;
    if (editing) {
      await api.updatePromptTemplate(editing.id, { name: name.trim(), content });
    } else {
      await api.createPromptTemplate(name.trim(), content);
    }
    setDialogOpen(false);
    await list.reload();
  };

  const onDelete = async (t: PromptTemplate) => {
    if (!confirm(`确定删除模板「${t.name}」？`)) return;
    await api.deletePromptTemplate(t.id);
    await list.reload();
  };

  return (
    <>
      <ResourceListLayout
        title="提示词模板"
        description="管理系统提示词模板，供智能体与流程编排复用。"
        searchPlaceholder="搜索模板名称"
        search={search}
        onSearchChange={setSearch}
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
            actions={
              <CardActions onEdit={() => openEdit(t)} onDelete={() => onDelete(t)} />
            }
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
    </>
  );
}
