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

export default function SkillsPage() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [name, setName] = useState("");
  const [tools, setTools] = useState("knowledge_search");
  const [snippet, setSnippet] = useState("");

  const list = usePagedList(useCallback((p, s) => api.listSkillPackages(p, s), []), { enabled: ready });

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (s) => `${s.name} ${s.tool_names.join(" ")}`),
    [list.items, search],
  );

  const onCreate = async () => {
    if (!name.trim()) return;
    await api.createSkillPackage({
      name: name.trim(),
      tool_names: tools
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      prompt_snippet: snippet || undefined,
    });
    setName("");
    setDialogOpen(false);
    await list.reload();
  };

  return (
    <>
      <ResourceListLayout
        title="技能包"
        description="将工具与提示词片段打包为可复用技能，便于智能体快速装配能力。"
        searchPlaceholder="搜索技能包名称"
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
          label="添加新技能包"
          hint="组合工具与提示词片段"
          onClick={() => setDialogOpen(true)}
        />
        {filtered.map((s) => (
          <ResourceItemCard
            key={s.id}
            title={s.name}
            description={s.prompt_snippet || s.description || "未配置提示词片段"}
            meta={<span>工具: {s.tool_names.join(", ") || "无"}</span>}
            actions={
              <button
                type="button"
                className="text-xs text-red-600 hover:underline"
                onClick={async (e) => {
                  e.stopPropagation();
                  await api.deleteSkillPackage(s.id);
                  await list.reload();
                }}
              >
                删除
              </button>
            }
          />
        ))}
      </ResourceListLayout>

      <ResourceDialog
        open={dialogOpen}
        title="创建技能包"
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
          placeholder="技能包名称"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          className="input-field w-full"
          placeholder="工具列表（逗号分隔）"
          value={tools}
          onChange={(e) => setTools(e.target.value)}
        />
        <textarea
          className="input-field h-20 w-full"
          placeholder="提示词片段（可选）"
          value={snippet}
          onChange={(e) => setSnippet(e.target.value)}
        />
      </ResourceDialog>
    </>
  );
}
