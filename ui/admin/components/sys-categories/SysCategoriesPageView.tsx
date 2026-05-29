"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { SysCategoriesDomainTabs, SysCategoriesTableSection, SysCategoryFormDialog } from "@/components/sys-categories/SysCategoriesSections";
import type { SysCategoriesPageVm } from "@/hooks/use-sys-categories-page";
import { SYS_CATEGORIES_PAGE_DESCRIPTION } from "@/lib/sys-categories-page-shared";

export function SysCategoriesPageView({ vm }: { vm: SysCategoriesPageVm }) {
  const { openCreate } = vm;

  return (
    <div>
      <PageHeader
        title="工作台分类"
        description={SYS_CATEGORIES_PAGE_DESCRIPTION}
        action={
          <button type="button" className="btn-primary" onClick={openCreate}>
            新建分类
          </button>
        }
      />

      <SysCategoriesDomainTabs vm={vm} />
      <SysCategoriesTableSection vm={vm} />
      <SysCategoryFormDialog vm={vm} />
    </div>
  );
}
