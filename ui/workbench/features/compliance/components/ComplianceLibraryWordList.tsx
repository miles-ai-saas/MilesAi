"use client";

import { CardActions } from "@/components/resource/CardActions";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { sensitiveActionLabel } from "@/features/compliance/lib/compliance-labels";
import type { ComplianceLibraryDetailVm } from "@/features/compliance/hooks/use-compliance-library-detail";
import type { EnumOption, LibraryWord, WordLibrary } from "@/lib/types";

type Props = {
  library: WordLibrary;
  vm: ComplianceLibraryDetailVm;
  sensitiveActions: EnumOption[];
};

export function ComplianceLibraryWordList({ library, vm, sensitiveActions }: Props) {
  const { words, openWord, onDeleteWord, toggleWordActive } = vm;

  return (
    <>
      <div className="resource-card-grid">
        {words.loading && words.items.length === 0 ? (
          <p className="col-span-full py-8 text-center text-sm text-ink-muted">加载词条…</p>
        ) : words.items.length === 0 ? (
          <p className="col-span-full rounded-xl border border-dashed border-line py-12 text-center text-sm text-ink-faint">
            本词库暂无词条，点击「添加词条」或「批量导入」
          </p>
        ) : (
          words.items.map((w: LibraryWord) => (
            <ResourceItemCard
              key={w.id}
              title={w.word}
              description={sensitiveActions.find((o) => o.value === w.action)?.hint ?? (w.action === "block" ? "命中后拦截请求" : "命中后记录警告日志")}
              badge={sensitiveActionLabel(w.action, null, sensitiveActions)}
              muted={!w.is_active}
              meta={<span>{w.is_active ? "已启用" : "本库内停用"}</span>}
              actions={
                <CardActions
                  onView={() => openWord("view", w)}
                  onEdit={() => openWord("edit", w)}
                  onDelete={() => onDeleteWord(w)}
                  actions={[
                    {
                      label: w.is_active ? "停用" : "启用",
                      onClick: () => void toggleWordActive(w),
                    },
                  ]}
                />
              }
            />
          ))
        )}
      </div>

      {!words.loading && words.items.length > 0 && (
        <ResourceListFooter
          page={words.page}
          size={words.size}
          total={words.total}
          onPageChange={words.setPage}
          onSizeChange={words.setSize}
          className="col-span-full"
        />
      )}
    </>
  );
}
