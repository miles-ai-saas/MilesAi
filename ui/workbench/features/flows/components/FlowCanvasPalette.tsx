"use client";

import { PALETTE_GROUPS, paletteItemsByGroup, type NodeType } from "@/lib/flow-nodes";

type Props = {
  open: boolean;
  onToggle: (open: boolean) => void;
  onDropPalette: (type: NodeType) => void;
};

export function FlowCanvasPalette({ open, onToggle, onDropPalette }: Props) {
  if (open) {
    return (
      <aside className="flex w-44 shrink-0 flex-col border-r border-line bg-surface sm:w-48">
        <div className="flex items-center justify-between border-b border-line px-2 py-2">
          <span className="text-xs font-semibold text-ink-muted">节点</span>
          <button type="button" className="btn-sm-ghost !px-1.5 text-[10px]" onClick={() => onToggle(false)} title="收起节点面板">
            ‹
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          <div className="flex flex-col gap-3">
            {PALETTE_GROUPS.map((group) => {
              const items = paletteItemsByGroup(group.key);
              if (!items.length) return null;
              return (
                <div key={group.key}>
                  <p className="mb-1 px-1 text-[10px] font-semibold uppercase tracking-wide text-ink-faint">{group.label}</p>
                  <div className="flex flex-col gap-1">
                    {items.map((item) => (
                      <button
                        key={item.type}
                        type="button"
                        onClick={() => onDropPalette(item.type)}
                        className="flex items-center gap-2 rounded-lg border border-line bg-surface px-2 py-2 text-left text-xs transition hover:border-brand/50 hover:bg-brand-light"
                      >
                        <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: item.color }} />
                        <span className="text-ink">{item.label}</span>
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
          <p className="mt-3 text-[10px] leading-relaxed text-ink-faint">选中节点在右侧编辑；Delete 删除；Ctrl+Z 撤销</p>
        </div>
      </aside>
    );
  }

  return (
    <div className="flex w-9 shrink-0 flex-col items-center border-r border-line bg-surface py-2">
      <button
        type="button"
        className="btn-sm-ghost !px-1 text-lg leading-none"
        onClick={() => onToggle(true)}
        title="展开节点面板"
        aria-label="展开节点面板"
      >
        ›
      </button>
    </div>
  );
}
