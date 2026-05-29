"use client";

import { useState } from "react";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { TagFilterDropdown } from "@/components/tag/TagFilterDropdown";
import { TagManageDialog } from "@/components/tag/TagManageDialog";
import { TagPicker } from "@/components/tag/TagPicker";
import { SkillCard } from "@/features/skills/components/SkillCard";
import { SkillImportGitDialog, SkillImportLocalDialog, SkillImportZipDialog } from "@/features/skills/components/SkillImportDialogs";
import type { SkillsPageVm } from "@/features/skills/hooks/use-skills-page";
import type { SysCategory } from "@/lib/types";

const SKILLS_PAGE_DESC = "管理 Cursor 风格 SKILL.md 技能目录；支持本地目录、ZIP 与 Git 导入，在智能体中绑定后注入系统提示。";

function SkillAddPanel({
  onCreateBlank,
  onImportLocal,
  onImportZip,
  onImportGit,
}: {
  onCreateBlank: () => void;
  onImportLocal: () => void;
  onImportZip: () => void;
  onImportGit: () => void;
}) {
  return (
    <div className="resource-card border border-dashed border-line-soft bg-surface-elevated/50 p-5">
      <p className="mb-3 text-sm font-medium text-ink">添加技能包</p>
      <ul className="space-y-2 text-sm text-brand">
        <li>
          <button type="button" className="hover:underline" onClick={onCreateBlank}>
            创建空白技能包
          </button>
        </li>
        <li>
          <button type="button" className="hover:underline" onClick={onImportLocal}>
            装载本地技能包
          </button>
        </li>
        <li>
          <button type="button" className="hover:underline" onClick={onImportZip}>
            导入技能压缩包
          </button>
        </li>
        <li>
          <button type="button" className="hover:underline" onClick={onImportGit}>
            下载 Git 技能包
          </button>
        </li>
      </ul>
    </div>
  );
}

function SkillCreateBlankDialog({
  open,
  categories,
  onClose,
  onSubmit,
}: {
  open: boolean;
  categories: SysCategory[];
  onClose: () => void;
  onSubmit: (name: string, description: string, categoryId: string, tagIds: string[]) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const generalId = categories.find((c) => c.slug === "general")?.id ?? categories[0]?.id ?? "";
  const effectiveCat = categoryId || generalId;

  const save = async () => {
    if (!name.trim() || !effectiveCat) return;
    setBusy(true);
    try {
      await onSubmit(name.trim(), description.trim(), effectiveCat, tagIds);
      setName("");
      setDescription("");
      onClose();
    } finally {
      setBusy(false);
    }
  };

  return (
    <ResourceDialog
      open={open}
      title="创建技能包"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={onClose}>
            取消
          </button>
          <button type="button" className="btn-primary" disabled={busy} onClick={save}>
            创建
          </button>
        </>
      }
    >
      <input className="input-field w-full" placeholder="技能名称" value={name} onChange={(e) => setName(e.target.value)} />
      <input className="input-field w-full" placeholder="描述（可选）" value={description} onChange={(e) => setDescription(e.target.value)} />
      <label className="block text-sm">
        <span className="mb-1 block text-ink-muted">分类</span>
        <select className="input-field w-full" value={effectiveCat} onChange={(e) => setCategoryId(e.target.value)}>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      <label className="block text-sm">
        <span className="mb-1 block text-ink-muted">标签</span>
        <TagPicker value={tagIds} onChange={setTagIds} />
      </label>
    </ResourceDialog>
  );
}

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
