"use client";

import { PromptTemplateDialog } from "@/features/prompts/components/PromptTemplateDialog";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { TagChips } from "@/components/tag/TagChips";
import { TagFilterDropdown } from "@/components/tag/TagFilterDropdown";
import { TagManageDialog } from "@/components/tag/TagManageDialog";
import type { PromptsPageVm } from "@/features/prompts/hooks/use-prompts-page";
import { promptActiveLabel } from "@/features/prompts/lib/prompt-labels";

function promptContentPreview(text: string, max = 120): string {
  const t = text.trim().replace(/\s+/g, " ");
  if (!t) return "（空正文）";
  if (t.length <= max) return t;
  return `${t.slice(0, max)}…`;
}

const PROMPTS_PAGE_DESC = "管理系统提示词（Markdown），供智能体 system prompt 与流程编排复用；支持按名称、正文或标签筛选。";

export function PromptsPageView({ vm }: { vm: PromptsPageVm }) {
  const {
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
  } = vm;

  return (
    <>
      <ResourceListLayout
        title="提示词模板"
        description={PROMPTS_PAGE_DESC}
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
                    await onImportFile(file);
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
            description={promptContentPreview(t.content)}
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
