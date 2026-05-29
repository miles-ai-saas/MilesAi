"use client";

/**
 * 知识库详情（链路 §8）：文档上传/轮询 status、`useKbMeta` 文案、`usePagedList` 文档与检索日志。
 */

import {
  DocumentChunksDrawer,
  KB_DETAIL_TABS,
  KbDetailDocumentsTab,
  KbDetailHeader,
  KbDetailLogsTab,
  KbDetailSearchTab,
  KbDetailSettingsDialog,
  KbDetailSkeleton,
  KbPageAlert,
  useKbDetailPage,
} from "@/features/kb";

export default function KbDetailPage() {
  const vm = useKbDetailPage();

  if (!vm.kb) {
    return <KbDetailSkeleton />;
  }

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <KbDetailHeader vm={vm} />

      {vm.alert ? <KbPageAlert tone={vm.alert.tone} message={vm.alert.message} onDismiss={() => vm.setAlert(null)} /> : null}

      <div className="flex gap-1 border-b border-line">
        {KB_DETAIL_TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => vm.setTab(t.key)}
            className={`rounded-t-lg px-4 py-2.5 text-sm transition ${
              vm.tab === t.key
                ? "bg-surface font-medium text-brand shadow-card ring-1 ring-line ring-b-0"
                : "text-ink-muted hover:bg-surface-muted/50 hover:text-ink"
            }`}
          >
            {t.label}
            {t.key === "documents" && vm.docs.total > 0 ? <span className="ml-1.5 text-xs text-ink-faint">({vm.docs.total})</span> : null}
          </button>
        ))}
      </div>

      {vm.tab === "documents" ? <KbDetailDocumentsTab vm={vm} /> : null}
      {vm.tab === "search" ? <KbDetailSearchTab vm={vm} /> : null}
      {vm.tab === "logs" ? <KbDetailLogsTab vm={vm} /> : null}

      {vm.confirmDialog}

      <DocumentChunksDrawer kbId={vm.id} doc={vm.chunksDoc} open={!!vm.chunksDoc} onClose={() => vm.setChunksDoc(null)} />

      <KbDetailSettingsDialog vm={vm} />
    </div>
  );
}
