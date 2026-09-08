"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/PageHeader";
import { ModelCatalogTableSection, ModelCatalogVendorFilterSection } from "@/features/model-catalog/components/ModelCatalogListSections";
import type { ModelCatalogPageVm } from "@/features/model-catalog/hooks/use-model-catalog-page";
import { MODEL_CATALOG_PAGE_DESCRIPTION } from "@/features/model-catalog/lib/model-catalog-page-shared";

export function ModelCatalogPageView({ vm }: { vm: ModelCatalogPageVm }) {
  return (
    <div>
      <PageHeader
        title="内置模型目录"
        description={MODEL_CATALOG_PAGE_DESCRIPTION}
        action={
          <Link href="/model-catalog/new" className="btn-primary">
            + 新建内置模型
          </Link>
        }
      />

      <ModelCatalogVendorFilterSection vm={vm} />
      <ModelCatalogTableSection vm={vm} />
    </div>
  );
}
