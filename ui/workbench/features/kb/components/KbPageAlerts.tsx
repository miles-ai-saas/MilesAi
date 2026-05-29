"use client";

import { KbPageAlert } from "@/features/kb/components/KbPageAlert";
import type { KbPageVm } from "@/features/kb/hooks/use-kb-page";

export function KbPageAlerts({ vm }: { vm: KbPageVm }) {
  const { listError, saveError, setSaveError, clearListError } = vm;
  if (!listError && !saveError) return null;

  return (
    <div className="resource-page-shell mb-4">
      {listError && <KbPageAlert tone="error" message={listError} onDismiss={clearListError} />}
      {saveError && (
        <div className={listError ? "mt-3" : ""}>
          <KbPageAlert tone="error" message={saveError} onDismiss={() => setSaveError("")} />
        </div>
      )}
    </div>
  );
}
