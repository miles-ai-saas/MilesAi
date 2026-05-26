"use client";

import {
  DAY_OPTIONS,
  HOUR_OPTIONS,
  MINUTE_OPTIONS,
  MONTH_OPTIONS,
  WEEK_OPTIONS,
  type CronParts,
} from "@/lib/cron-celery";

type Props = {
  parts: CronParts;
  onChange: (parts: CronParts) => void;
};

const FIELDS: {
  key: keyof CronParts;
  label: string;
  options: { value: string; label: string }[];
}[] = [
  { key: "minute", label: "分", options: MINUTE_OPTIONS },
  { key: "hour", label: "时", options: HOUR_OPTIONS },
  { key: "dayOfMonth", label: "日", options: DAY_OPTIONS },
  { key: "month", label: "月", options: MONTH_OPTIONS },
  { key: "dayOfWeek", label: "周", options: WEEK_OPTIONS },
];

export function CronFieldPicker({ parts, onChange }: Props) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {FIELDS.map(({ key, label, options }) => (
        <label key={key} className="block text-sm">
          <span className="mb-1 block text-ink-muted">{label}</span>
          <select
            className="input-field w-full"
            value={parts[key]}
            onChange={(e) => onChange({ ...parts, [key]: e.target.value })}
          >
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
      ))}
    </div>
  );
}
