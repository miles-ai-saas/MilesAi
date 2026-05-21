"use client";

import { useCallback, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { filterBySearch } from "@/lib/filter-search";

export default function KbPage() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const list = usePagedList(useCallback((p, s) => api.listKbs(p, s), []), { enabled: ready });

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (kb) => `${kb.name} ${kb.description ?? ""}`),
    [list.items, search],
  );

  const onCreate = async () => {
    await api.createKb(name.trim() || `知识库 ${list.total + 1}`, description || undefined);
    setName("");
    setDescription("");
    setDialogOpen(false);
    await list.reload();
  };

  return (
    <>
      <ResourceListLayout
        title="知识库"
        description="管理企业知识库与文档，为智能体 RAG 检索与流程节点提供知识来源。"
        searchPlaceholder="搜索知识库名称"
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
        <AddResourceCard
          label="添加新知识库"
          hint="创建知识库并上传文档"
          onClick={() => setDialogOpen(true)}
        />
        {filtered.map((kb) => (
          <ResourceItemCard
            key={kb.id}
            href={`/kb/${kb.id}`}
            title={kb.name}
            description={kb.description || "点击进入管理文档与切片"}
            meta={<span className="text-brand">管理文档 →</span>}
          />
        ))}
      </ResourceListLayout>

      <ResourceDialog
        open={dialogOpen}
        title="新建知识库"
        onClose={() => setDialogOpen(false)}
        footer={
          <>
            <button type="button" className="btn-ghost" onClick={() => setDialogOpen(false)}>
              取消
            </button>
            <button type="button" className="btn-primary" onClick={onCreate}>
              创建
            </button>
          </>
        }
      >
        <input
          className="input-field w-full"
          placeholder="知识库名称"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          className="input-field w-full"
          placeholder="描述（可选）"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </ResourceDialog>
    </>
  );
}
