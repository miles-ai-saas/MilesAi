"use client";

import { useMemo, useState } from "react";
import { CodeEditor } from "@/components/editor/CodeEditor";
import { MarkdownPreview } from "@/components/editor/MarkdownPreview";
import { parseSkillMd } from "@/lib/skill-md";

type ViewMode = "edit" | "preview" | "split";

type Props = {
  path: string;
  value: string;
  onChange: (value: string) => void;
};

function ViewModeTabs({
  mode,
  onChange,
}: {
  mode: ViewMode;
  onChange: (mode: ViewMode) => void;
}) {
  const tabs: { key: ViewMode; label: string }[] = [
    { key: "edit", label: "编辑" },
    { key: "split", label: "分栏" },
    { key: "preview", label: "预览" },
  ];
  return (
    <div className="inline-flex rounded-lg border border-line bg-surface-muted/50 p-0.5">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          onClick={() => onChange(tab.key)}
          className={`rounded-md px-2.5 py-1 text-xs transition ${
            mode === tab.key
              ? "bg-surface font-medium text-brand shadow-sm"
              : "text-ink-muted hover:text-ink"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

function FrontmatterPanel({ frontmatter }: { frontmatter: Record<string, string> }) {
  const entries = Object.entries(frontmatter);
  if (entries.length === 0) {
    return (
      <p className="mb-3 rounded-lg border border-dashed border-line px-3 py-2 text-xs text-ink-faint">
        无 YAML frontmatter；SKILL.md 建议以 <code className="text-brand">---</code> 块开头。
      </p>
    );
  }
  return (
    <dl className="mb-3 space-y-2 rounded-lg border border-line bg-surface-muted/40 px-3 py-2 text-xs">
      <p className="font-medium text-ink-muted">Frontmatter</p>
      {entries.map(([key, val]) => (
        <div key={key} className="grid gap-0.5 sm:grid-cols-[5.5rem_1fr]">
          <dt className="font-mono text-ink-faint">{key}</dt>
          <dd className="break-words text-ink">{val || "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

export function SkillMarkdownSplitEditor({ path, value, onChange }: Props) {
  const [viewMode, setViewMode] = useState<ViewMode>("split");
  const { frontmatter, body } = useMemo(() => parseSkillMd(value), [value]);

  const showEdit = viewMode === "edit" || viewMode === "split";
  const showPreview = viewMode === "preview" || viewMode === "split";

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-ink-muted">{path}</p>
        <ViewModeTabs mode={viewMode} onChange={setViewMode} />
      </div>

      <div
        className={`flex min-h-0 flex-1 gap-3 ${
          viewMode === "split" ? "flex-col lg:flex-row" : "flex-col"
        }`}
      >
        {showEdit && (
          <div
            className={`flex min-h-0 min-w-0 flex-col ${
              viewMode === "split" ? "min-h-[240px] flex-1 lg:min-h-0" : "flex-1"
            }`}
          >
            <CodeEditor
              fill
              language="markdown"
              value={value}
              onChange={onChange}
              aria-label={`编辑 ${path}`}
            />
          </div>
        )}

        {showPreview && (
          <section
            className={`flex min-h-0 min-w-0 flex-col overflow-hidden rounded-lg border border-line bg-surface ${
              viewMode === "split" ? "min-h-[240px] flex-1 lg:min-h-0" : "flex-1"
            }`}
          >
            <header className="shrink-0 border-b border-line-soft px-4 py-2 text-xs font-medium text-ink-muted">
              预览
            </header>
            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
              <FrontmatterPanel frontmatter={frontmatter} />
              <MarkdownPreview content={body} />
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
