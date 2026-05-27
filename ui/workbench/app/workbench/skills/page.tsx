"use client";

/** 技能包列表（链路 §3）；SKILL.md 编辑见 skills/[id]（§9）。 */

/**
 * 技能包列表：分类 Tab、标签筛选、添加/导入入口、卡片跳转编辑器。
 */

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { CardActions } from "@/components/resource/CardActions";
import { filterBySearch } from "@/lib/filter-search";
import { useCategoryTabs } from "@/components/category/useCategoryTabs";
import { TagChips } from "@/components/tag/TagChips";
import { TagFilterDropdown } from "@/components/tag/TagFilterDropdown";
import { TagManageDialog } from "@/components/tag/TagManageDialog";
import { SkillCreateBlankDialog } from "@/components/skills/SkillCreateBlankDialog";
import {
  SkillImportGitDialog,
  SkillImportLocalDialog,
  SkillImportZipDialog,
} from "@/components/skills/SkillImportDialogs";
import { skillActiveLabel, skillSourceTypeLabel } from "@/lib/skill-labels";
import { useSkillMeta } from "@/hooks/use-skill-meta";
import type { SkillImportResult, SkillMeta, SkillPackage } from "@/lib/types";

function formatUpdated(iso: string) {
  try {
    const d = new Date(iso);
    return d.toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function SkillsPage() {
  const router = useRouter();
  const { ready } = useRequireAuth();
  const skillMeta = useSkillMeta(ready);
  const [search, setSearch] = useState("");
  const cat = useCategoryTabs("skill");
  const [tagFilterIds, setTagFilterIds] = useState<string[]>([]);
  const [tagManageOpen, setTagManageOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [importLocal, setImportLocal] = useState(false);
  const [importZip, setImportZip] = useState(false);
  const [importGit, setImportGit] = useState(false);
  const [importMsg, setImportMsg] = useState<string | null>(null);

  const list = usePagedList(
    useCallback(
      (p, s) =>
        api.listSkillPackages(
          p,
          s,
          cat.activeCategoryId,
          tagFilterIds.length ? tagFilterIds : undefined,
        ),
      [cat.activeCategoryId, tagFilterIds],
    ),
    { enabled: ready, resetKey: `${cat.activeId}-${tagFilterIds.join(",")}` },
  );

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (s) => `${s.name} ${s.slug} ${s.description ?? ""}`),
    [list.items, search],
  );

  const onImportDone = (result: SkillImportResult) => {
    const parts = [`导入 ${result.imported} 个`, `跳过 ${result.skipped} 个`];
    if (result.errors.length) parts.push(`错误: ${result.errors.join("; ")}`);
    setImportMsg(parts.join("，"));
    void list.reload();
    void cat.reload();
  };

  const onCreateBlank = async (
    name: string,
    description: string,
    categoryId: string,
    tagIds: string[],
  ) => {
    const row = await api.createSkillPackageBlank({
      name,
      description: description || undefined,
      category_id: categoryId,
      tag_ids: tagIds,
    });
    router.push(`/workbench/skills/${row.id}`);
  };

  return (
    <>
      <ResourceListLayout
        title="技能包"
        description="管理 Cursor 风格 SKILL.md 技能目录；支持本地目录、ZIP 与 Git 导入，在智能体中绑定后注入系统提示。"
        searchPlaceholder="搜索技能包"
        search={search}
        onSearchChange={setSearch}
        tabs={cat.tabs}
        activeTab={cat.activeId}
        onTabChange={cat.setActiveId}
        loading={list.loading}
        headerAction={
          <div className="flex flex-wrap items-center gap-2">
            <TagFilterDropdown value={tagFilterIds} onChange={setTagFilterIds} />
            <button
              type="button"
              className="text-sm text-brand hover:underline"
              onClick={() => setTagManageOpen(true)}
            >
              管理标签
            </button>
          </div>
        }
        footer={
          !list.loading ? (
            <ResourceListFooter
              page={list.page}
              size={list.size}
              total={list.total}
              onPageChange={list.setPage}
              onSizeChange={list.setSize}
            />
          ) : null
        }
      >
        <div className="resource-card border border-dashed border-line-soft bg-surface-elevated/50 p-5">
          <p className="mb-3 text-sm font-medium text-ink">添加技能包</p>
          <ul className="space-y-2 text-sm text-brand">
            <li>
              <button type="button" className="hover:underline" onClick={() => setCreateOpen(true)}>
                创建空白技能包
              </button>
            </li>
            <li>
              <button type="button" className="hover:underline" onClick={() => setImportLocal(true)}>
                装载本地技能包
              </button>
            </li>
            <li>
              <button type="button" className="hover:underline" onClick={() => setImportZip(true)}>
                导入技能压缩包
              </button>
            </li>
            <li>
              <button type="button" className="hover:underline" onClick={() => setImportGit(true)}>
                下载 Git 技能包
              </button>
            </li>
          </ul>
        </div>

        {importMsg ? (
          <p className="col-span-full rounded-md bg-brand/10 px-3 py-2 text-sm text-brand">{importMsg}</p>
        ) : null}

        {filtered.map((s) => (
          <SkillCard
            key={s.id}
            skill={s}
            skillMeta={skillMeta}
            onOpen={() => router.push(`/workbench/skills/${s.id}`)}
            onDelete={async () => {
              await api.deleteSkillPackage(s.id);
              await list.reload();
            }}
            onToggle={async () => {
              await api.updateSkillPackage(s.id, { is_active: !s.is_active });
              await list.reload();
            }}
          />
        ))}
      </ResourceListLayout>

      <SkillCreateBlankDialog
        open={createOpen}
        categories={cat.categories}
        onClose={() => setCreateOpen(false)}
        onSubmit={onCreateBlank}
      />
      <SkillImportLocalDialog
        open={importLocal}
        categories={cat.categories}
        onClose={() => setImportLocal(false)}
        onDone={onImportDone}
      />
      <SkillImportZipDialog
        open={importZip}
        categories={cat.categories}
        onClose={() => setImportZip(false)}
        onDone={onImportDone}
      />
      <SkillImportGitDialog
        open={importGit}
        categories={cat.categories}
        onClose={() => setImportGit(false)}
        onDone={onImportDone}
      />
      <TagManageDialog open={tagManageOpen} onClose={() => setTagManageOpen(false)} />
    </>
  );
}

function SkillCard({
  skill,
  skillMeta,
  onOpen,
  onDelete,
  onToggle,
}: {
  skill: SkillPackage;
  skillMeta: SkillMeta | null;
  onOpen: () => void;
  onDelete: () => Promise<void>;
  onToggle: () => Promise<void>;
}) {
  return (
    <ResourceItemCard
      title={skill.name}
      description={skill.description || "暂无描述"}
      badge={
        skill.is_active
          ? skillSourceTypeLabel(skill.source_type, skillMeta)
          : skillActiveLabel(false, skillMeta)
      }
      onClick={onOpen}
      meta={
        <>
          <span className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
            {skill.category_name ? (
              <span className="rounded bg-surface-muted px-1.5 py-0.5">{skill.category_name}</span>
            ) : null}
            <span>更新于 {formatUpdated(skill.updated_at)}</span>
          </span>
          <TagChips tags={skill.tags} />
        </>
      }
      actions={
        <CardActions
          actions={[
            { label: "编辑", onClick: onOpen, variant: "primary" },
            { label: skill.is_active ? "停用" : "启用", onClick: onToggle },
            { label: "删除", onClick: onDelete, variant: "danger" },
          ]}
        />
      }
    />
  );
}
