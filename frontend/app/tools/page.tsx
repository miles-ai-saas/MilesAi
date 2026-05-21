"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { filterBySearch } from "@/lib/filter-search";

export default function ToolsPage() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [builtin, setBuiltin] = useState<Record<string, string>[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");

  const list = usePagedList(useCallback((p, s) => api.listCustomTools(p, s), []), { enabled: ready });

  useEffect(() => {
    if (!ready) return;
    api.listBuiltinTools().then(setBuiltin);
  }, [ready]);

  const filteredBuiltin = useMemo(
    () => filterBySearch(builtin, search, (t) => `${t.name} ${t.description}`),
    [builtin, search],
  );
  const filteredCustom = useMemo(
    () => filterBySearch(list.items, search, (t) => `${t.name} ${t.description ?? ""}`),
    [list.items, search],
  );

  const onCreate = async () => {
    if (!name.trim()) return;
    await api.createCustomTool(name.trim(), desc, { url: "", method: "GET" });
    setName("");
    setDesc("");
    setDialogOpen(false);
    await list.reload();
  };

  return (
    <>
      <ResourceListLayout
        title="工具"
        description="管理平台内置工具与自定义 HTTP 工具，供技能包与智能体调用。"
        searchPlaceholder="搜索工具名称"
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
          label="添加自定义工具"
          hint="注册 HTTP 工具供编排使用"
          onClick={() => setDialogOpen(true)}
        />
        {filteredBuiltin.map((t) => (
          <ResourceItemCard
            key={`builtin-${t.name}`}
            title={t.name}
            description={t.description}
            badge="内置"
          />
        ))}
        {filteredCustom.map((t) => (
          <ResourceItemCard
            key={t.id}
            title={t.name}
            description={t.description ?? "自定义 HTTP 工具"}
            badge="自定义"
          />
        ))}
      </ResourceListLayout>

      <ResourceDialog
        open={dialogOpen}
        title="添加自定义工具"
        onClose={() => setDialogOpen(false)}
        footer={
          <>
            <button type="button" className="btn-ghost" onClick={() => setDialogOpen(false)}>
              取消
            </button>
            <button type="button" className="btn-primary" onClick={onCreate}>
              添加
            </button>
          </>
        }
      >
        <input
          className="input-field w-full"
          placeholder="名称"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          className="input-field w-full"
          placeholder="描述"
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
        />
      </ResourceDialog>
    </>
  );
}
