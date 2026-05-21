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
import type { SkillPackage } from "@/lib/types";

export default function SkillsPage() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<SkillPackage | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedTools, setSelectedTools] = useState<string[]>(["knowledge_search"]);
  const [catalog, setCatalog] = useState<
    { source: string; name: string; description?: string | null }[]
  >([]);
  const [snippet, setSnippet] = useState("");

  const list = usePagedList(useCallback((p, s) => api.listSkillPackages(p, s), []), { enabled: ready });

  useEffect(() => {
    if (!ready) return;
    api.listToolCatalog().then(setCatalog);
  }, [ready]);

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (s) => `${s.name} ${s.tool_names.join(" ")}`),
    [list.items, search],
  );

  const openCreate = () => {
    setEditing(null);
    setName("");
    setDescription("");
    setSelectedTools(["knowledge_search"]);
    setSnippet("");
    setDialogOpen(true);
  };

  const openEdit = (s: SkillPackage) => {
    setEditing(s);
    setName(s.name);
    setDescription(s.description ?? "");
    setSelectedTools(s.tool_names.length ? s.tool_names : []);
    setSnippet(s.prompt_snippet ?? "");
    setDialogOpen(true);
  };

  const toggleTool = (toolName: string) => {
    setSelectedTools((prev) =>
      prev.includes(toolName) ? prev.filter((t) => t !== toolName) : [...prev, toolName],
    );
  };

  const onSave = async () => {
    if (!name.trim()) return;
    const tool_names = selectedTools;
    if (editing) {
      await api.updateSkillPackage(editing.id, {
        name: name.trim(),
        description: description.trim() || undefined,
        tool_names,
        prompt_snippet: snippet.trim() || undefined,
      });
    } else {
      await api.createSkillPackage({
        name: name.trim(),
        description: description.trim() || undefined,
        tool_names,
        prompt_snippet: snippet.trim() || undefined,
      });
    }
    setDialogOpen(false);
    await list.reload();
  };

  return (
    <>
      <ResourceListLayout
        title="技能包"
        description="将工具名与提示词片段打包；在智能体表单中绑定后自动注入系统提示。"
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
          onClick={openCreate}
        />
        {filtered.map((s) => (
          <ResourceItemCard
            key={s.id}
            title={s.name}
            description={s.prompt_snippet || s.description || "未配置提示词片段"}
            badge={s.is_active ? undefined : "已停用"}
            meta={<span>工具: {s.tool_names.join(", ") || "无"}</span>}
            actions={
              <span className="flex gap-3">
                <button
                  type="button"
                  className="text-xs text-brand hover:underline"
                  onClick={(e) => {
                    e.stopPropagation();
                    openEdit(s);
                  }}
                >
                  编辑
                </button>
                <button
                  type="button"
                  className="text-xs text-ink-muted hover:underline"
                  onClick={async (e) => {
                    e.stopPropagation();
                    await api.updateSkillPackage(s.id, { is_active: !s.is_active });
                    await list.reload();
                  }}
                >
                  {s.is_active ? "停用" : "启用"}
                </button>
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
              </span>
            }
          />
        ))}
      </ResourceListLayout>

      <ResourceDialog
        open={dialogOpen}
        title={editing ? "编辑技能包" : "创建技能包"}
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
          placeholder="技能包名称"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          className="input-field w-full"
          placeholder="描述（可选）"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <div className="max-h-40 overflow-y-auto rounded border border-line-soft p-2">
          <p className="mb-2 text-xs font-medium text-ink-muted">从工具目录选择</p>
          {catalog.length === 0 && <p className="text-xs text-ink-faint">加载中…</p>}
          {catalog.map((t) => (
            <label key={`${t.source}-${t.name}`} className="flex cursor-pointer items-center gap-2 py-1 text-xs">
              <input
                type="checkbox"
                checked={selectedTools.includes(t.name)}
                onChange={() => toggleTool(t.name)}
              />
              <span>
                {t.name}
                <span className="text-ink-faint"> ({t.source})</span>
              </span>
            </label>
          ))}
        </div>
        <textarea
          className="input-field h-24 w-full"
          placeholder="提示词片段（注入智能体系统提示）"
          value={snippet}
          onChange={(e) => setSnippet(e.target.value)}
        />
      </ResourceDialog>
    </>
  );
}
