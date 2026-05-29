"use client";

import type { ToolKindTab } from "@/features/tools/lib/tool-labels";
import type { ToolCreateDialogKindTab } from "@/features/tools/lib/tool-create-dialog-shared";

export function ToolCreateDialogKindSelector({
  kindTabs,
  toolKind,
  kindLocked,
  onToolKindChange,
}: {
  kindTabs: ToolCreateDialogKindTab[];
  toolKind: ToolKindTab;
  kindLocked: boolean;
  onToolKindChange: (v: ToolKindTab) => void;
}) {
  if (kindLocked) return null;

  return (
    <div className="inline-flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1">
      {kindTabs.map((tab) => {
        const active = toolKind === tab.key;
        return (
          <button
            key={tab.key}
            type="button"
            disabled={!tab.available}
            title={tab.hint}
            onClick={() => tab.available && onToolKindChange(tab.key)}
            className={`rounded-lg px-4 py-2 text-left transition ${
              active
                ? "bg-brand-light text-brand shadow-sm ring-1 ring-brand/20"
                : tab.available
                  ? "text-ink-muted hover:bg-surface-muted hover:text-ink"
                  : "cursor-not-allowed opacity-50"
            }`}
          >
            <span className="text-sm font-medium">{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}
