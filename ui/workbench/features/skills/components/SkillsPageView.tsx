"use client";

import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { TagFilterDropdown } from "@/components/tag/TagFilterDropdown";
import { TagManageDialog } from "@/components/tag/TagManageDialog";
import { SkillAddPanel } from "@/features/skills/components/SkillAddPanel";
import { SkillCard } from "@/features/skills/components/SkillCard";
import { SkillCreateBlankDialog } from "@/features/skills/components/SkillCreateBlankDialog";
import { SkillImportGitDialog, SkillImportLocalDialog, SkillImportZipDialog } from "@/features/skills/components/SkillImportDialogs";
import type { SkillsPageVm } from "@/features/skills/hooks/use-skills-page";
import { SKILLS_PAGE_DESC } from "@/features/skills/lib/skills-page-shared";

export function SkillsPageView({ vm }: { vm: SkillsPageVm }) {
  const {
    skillMeta,
    search,
    setSearch,
    cat,
    tagFilterIds,
    setTagFilterIds,
    tagManageOpen,
    setTagManageOpen,
    createOpen,
    setCreateOpen,
    importLocal,
    setImportLocal,
    importZip,
    setImportZip,
    importGit,
    setImportGit,
    importMsg,
    list,
    filtered,
    onImportDone,
    onCreateBlank,
    openSkill,
    onDeleteSkill,
    onToggleSkill,
  } = vm;

  return (
    <>
      <ResourceListLayout
        title="技能包"
        description={SKILLS_PAGE_DESC}
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
            <button type="button" className="text-sm text-brand hover:underline" onClick={() => setTagManageOpen(true)}>
              管理标签
            </button>
          </div>
        }
        footer={
          !list.loading ? (
            <ResourceListFooter page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
          ) : null
        }
      >
        <SkillAddPanel
          onCreateBlank={() => setCreateOpen(true)}
          onImportLocal={() => setImportLocal(true)}
          onImportZip={() => setImportZip(true)}
          onImportGit={() => setImportGit(true)}
        />

        {importMsg ? <p className="col-span-full rounded-md bg-brand/10 px-3 py-2 text-sm text-brand">{importMsg}</p> : null}

        {filtered.map((s) => (
          <SkillCard
            key={s.id}
            skill={s}
            skillMeta={skillMeta}
            onOpen={() => openSkill(s.id)}
            onDelete={() => onDeleteSkill(s.id)}
            onToggle={() => onToggleSkill(s.id, s.is_active)}
          />
        ))}
      </ResourceListLayout>

      <SkillCreateBlankDialog open={createOpen} categories={cat.categories} onClose={() => setCreateOpen(false)} onSubmit={onCreateBlank} />
      <SkillImportLocalDialog open={importLocal} categories={cat.categories} onClose={() => setImportLocal(false)} onDone={onImportDone} />
      <SkillImportZipDialog open={importZip} categories={cat.categories} onClose={() => setImportZip(false)} onDone={onImportDone} />
      <SkillImportGitDialog open={importGit} categories={cat.categories} onClose={() => setImportGit(false)} onDone={onImportDone} />
      <TagManageDialog open={tagManageOpen} onClose={() => setTagManageOpen(false)} />
    </>
  );
}
