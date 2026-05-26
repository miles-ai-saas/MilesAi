"use client";

import { CRON_PRESETS, partsEqual, type CronParts } from "@/lib/cron-celery";

type Props = {
  parts: CronParts;
  onSelect: (parts: CronParts) => void;
};

export function CronPresetLinks({ parts, onSelect }: Props) {
  return (
    <div className="space-y-2">
      <p className="text-sm text-ink-muted">常用</p>
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {CRON_PRESETS.map((preset) => {
          const active = partsEqual(parts, preset.parts);
          return (
            <button
              key={preset.label}
              type="button"
              onClick={() => onSelect(preset.parts)}
              className={`text-xs transition hover:underline ${
                active ? "font-medium text-brand" : "text-brand"
              }`}
            >
              {preset.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
