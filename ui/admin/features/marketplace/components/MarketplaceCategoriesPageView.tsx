"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { MarketplaceCategoriesTableSection, MarketplaceCategoryFormDialog } from "@/features/marketplace/components/MarketplaceCategoriesSections";
import type { MarketplaceCategoriesPageVm } from "@/features/marketplace/hooks/use-marketplace-categories-page";
import { MARKETPLACE_CATEGORIES_PAGE_DESCRIPTION } from "@/features/marketplace/lib/marketplace-categories-page-shared";

export function MarketplaceCategoriesPageView({ vm }: { vm: MarketplaceCategoriesPageVm }) {
  const { openCreate } = vm;

  return (
    <div>
      <PageHeader
        title="应用市场分类"
        description={MARKETPLACE_CATEGORIES_PAGE_DESCRIPTION}
        action={
          <button type="button" className="btn-primary" onClick={openCreate}>
            新建分类
          </button>
        }
      />

      <MarketplaceCategoriesTableSection vm={vm} />
      <MarketplaceCategoryFormDialog vm={vm} />
    </div>
  );
}
