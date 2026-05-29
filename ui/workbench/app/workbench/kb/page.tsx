"use client";

/** 知识库列表（链路 §3 + §8）；详情与文档入库见 kb/[id]。 */

import { KbCatalogView, KbFormDialog, KbPageAlert, useKbPage } from "@/features/kb";

export default function KbPage() {
  const vm = useKbPage();
  const { listError, saveError, setSaveError, clearListError } = vm;

  return (
    <>
      {(listError || saveError) && (
        <div className="resource-page-shell mb-4">
          {listError && <KbPageAlert tone="error" message={listError} onDismiss={clearListError} />}
          {saveError && (
            <div className={listError ? "mt-3" : ""}>
              <KbPageAlert tone="error" message={saveError} onDismiss={() => setSaveError("")} />
            </div>
          )}
        </div>
      )}
      <KbCatalogView vm={vm} />
      <KbFormDialog vm={vm} />
      {vm.confirmDialog}
    </>
  );
}
