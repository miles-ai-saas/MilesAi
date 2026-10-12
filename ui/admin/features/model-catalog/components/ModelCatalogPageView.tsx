"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/PageHeader";
import { ModelCatalogTableSection, ModelCatalogVendorFilterSection } from "@/features/model-catalog/components/ModelCatalogListSections";
import type { ModelCatalogPageVm } from "@/features/model-catalog/hooks/use-model-catalog-page";
import { MODEL_CATALOG_PAGE_DESCRIPTION } from "@/features/model-catalog/lib/model-catalog-page-shared";

export function ModelCatalogPageView({ vm }: { vm: ModelCatalogPageVm }) {
  return (
    <div className="admin-page-stack">
      <PageHeader
        title="内置模型目录"
        description={MODEL_CATALOG_PAGE_DESCRIPTION}
        action={
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-ghost" onClick={() => vm.setImportOpen(true)}>
              批量导入
            </button>
            <Link href="/model-catalog/new" className="btn-primary">
              + 新建内置模型
            </Link>
          </div>
        }
      />

      <ModelCatalogVendorFilterSection vm={vm} />
      <ModelCatalogTableSection vm={vm} />

      {vm.importOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="card max-h-[90vh] w-full max-w-2xl overflow-auto p-5 shadow-lg">
            <h2 className="text-base font-semibold text-ink">批量导入 JSON</h2>
            <p className="mt-1 text-xs cell-muted">
              格式：{"{"} &quot;items&quot;: [ &#123; name, vendor, model_name, model_code, … &#125; ], &quot;upsert&quot;: true {"}"}。按
              model_code 新建或更新元数据（不覆盖已有 Key）。
            </p>
            <textarea
              className="input-field mt-3 min-h-[240px] w-full resize-y font-mono text-xs"
              value={vm.importText}
              onChange={(e) => vm.setImportText(e.target.value)}
              spellCheck={false}
            />
            {vm.importErr ? <p className="mt-2 text-sm text-red-600">{vm.importErr}</p> : null}
            {vm.importMsg ? <p className="mt-2 text-sm text-emerald-700">{vm.importMsg}</p> : null}
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" className="btn-ghost" disabled={vm.importBusy} onClick={() => vm.setImportOpen(false)}>
                关闭
              </button>
              <button type="button" className="btn-primary" disabled={vm.importBusy} onClick={() => void vm.onImport()}>
                {vm.importBusy ? "导入中…" : "导入"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
