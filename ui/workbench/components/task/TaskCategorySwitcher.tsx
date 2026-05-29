"use client";

import { TASK_CATEGORY_TABS, type TaskCategory } from "@/lib/tasks-page-shared";

export function TaskCategorySwitcher({ category, onChange }: { category: TaskCategory; onChange: (c: TaskCategory) => void }) {
  return (
    <div className="mb-4 flex gap-2">
      {TASK_CATEGORY_TABS.map((tab) => (
        <button
          key={tab.key}
          type="button"
          onClick={() => onChange(tab.key)}
          className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
            category === tab.key ? "bg-brand text-white shadow-sm" : "bg-surface text-ink-muted ring-1 ring-line hover:text-ink"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
