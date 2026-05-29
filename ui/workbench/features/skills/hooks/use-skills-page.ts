"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useCategoryTabs } from "@/components/category/useCategoryTabs";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useSkillMeta } from "@/hooks/use-skill-meta";
import { filterBySearch } from "@/lib/filter-search";
import type { SkillImportResult } from "@/lib/types";

export function useSkillsPage() {
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
      (p, s) => api.listSkillPackages(p, s, cat.activeCategoryId, tagFilterIds.length ? tagFilterIds : undefined),
      [cat.activeCategoryId, tagFilterIds],
    ),
    { enabled: ready, resetKey: `${cat.activeId}-${tagFilterIds.join(",")}` },
  );

  const filtered = useMemo(() => filterBySearch(list.items, search, (s) => `${s.name} ${s.slug} ${s.description ?? ""}`), [list.items, search]);

  const onImportDone = (result: SkillImportResult) => {
    const parts = [`导入 ${result.imported} 个`, `跳过 ${result.skipped} 个`];
    if (result.errors.length) parts.push(`错误: ${result.errors.join("; ")}`);
    setImportMsg(parts.join("，"));
    void list.reload();
    void cat.reload();
  };

  const onCreateBlank = async (name: string, description: string, categoryId: string, tagIds: string[]) => {
    const row = await api.createSkillPackageBlank({
      name,
      description: description || undefined,
      category_id: categoryId,
      tag_ids: tagIds,
    });
    router.push(`/workbench/skills/${row.id}`);
  };

  const openSkill = (id: string) => {
    router.push(`/workbench/skills/${id}`);
  };

  const onDeleteSkill = async (id: string) => {
    await api.deleteSkillPackage(id);
    await list.reload();
  };

  const onToggleSkill = async (id: string, isActive: boolean) => {
    await api.updateSkillPackage(id, { is_active: !isActive });
    await list.reload();
  };

  return {
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
  };
}

export type SkillsPageVm = ReturnType<typeof useSkillsPage>;
