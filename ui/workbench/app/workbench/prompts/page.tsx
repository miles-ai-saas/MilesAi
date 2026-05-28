"use client";

/** 提示词模板列表（链路 §3 + §4 `usePromptMeta`）。 */

import { useCallback, useMemo, useState } from "react";
import { PromptTemplateDialog, type PromptTemplateDialogMode } from "@/components/prompt/PromptTemplateDialog";
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
import { TagFilterDropdown } from "@/components/tag/TagFilterDropdown";
import { TagManageDialog } from "@/components/tag/TagManageDialog";
import { promptActiveLabel } from "@/lib/prompt-labels";
import { usePromptMeta } from "@/hooks/use-prompt-meta";
import type { PromptTemplate } from "@/lib/types";

function contentPreview(text: string, max = 120): string {
  const t = text.trim().replace(/\s+/g, " ");
  if (!t) return "（空正文）";
  if (t.length <= max) return t;
  return `${t.slice(0, max)}…`;
}

export default function PromptsPage() {
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
            <TagFilterDropdown value={tagFilterIds} onChange={setTagFilterIds} />
            <button type="button" className="btn-sm-outline" onClick={() => setTagManageOpen(true)}>
              管理标签
            </button>
            <label className="btn-sm-outline cursor-pointer">
              导入
              <input
                type="file"
                accept=".json"
                className="hidden"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  try {
                    const text = await file.text();
                    const pkg = JSON.parse(text);
                    const t = pkg.agent || pkg;
                    if (!t.name || !t.content) {
                      alert("JSON 格式错误：需要 name 和 content 字段");
                      return;
                    }
                    await api.createPromptTemplate(t.name, t.content, t.category_id, t.tag_ids ?? t.tags?.map((tg: { id: string }) => tg.id));
                    await list.reload();
                  } catch (err) {
                    alert(`导入失败: ${err instanceof Error ? err.message : err}`);
                  }
                }}
              />
            </label>
            <button type="button" className="btn-sm-primary" onClick={openCreate}>
              新建模板
            </button>
          </div>
        }
        loading={list.loading}
        footer={
          !list.loading ? (
            <ResourceListFooter page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
          ) : null
        }
      >
        <AddResourceCard label="新建提示词模板" hint="Markdown 正文 · 编辑 / 预览" onClick={openCreate} />
        {filtered.map((t) => (
          <ResourceItemCard
            key={t.id}
            title={t.name}
            description={contentPreview(t.content)}
            badge={promptActiveLabel(t.is_active, promptMeta)}
            meta={
              <div className="space-y-2">
                <span className="inline-block rounded border border-line px-1.5 py-px text-[10px] text-ink-faint">Markdown</span>
                <TagChips tags={t.tags} />
              </div>
            }
            actions={
              <CardActions
                actions={[{ label: "导出", onClick: () => onExport(t) }]}
                onView={() => openView(t)}
                onEdit={() => openEdit(t)}
                onDelete={() => onDelete(t)}
              />
            }
          />
        ))}
      </ResourceListLayout>

      <PromptTemplateDialog
        open={dialogOpen}
        mode={dialogMode}
        template={editing}
        onClose={() => setDialogOpen(false)}
        onSaved={() => list.reload()}
        onRequestEdit={
          editing
            ? () => {
                setDialogMode("edit");
              }
            : undefined
        }
      />
      <TagManageDialog open={tagManageOpen} onClose={() => setTagManageOpen(false)} />
      {confirmDialog}
    </>
  );
}
