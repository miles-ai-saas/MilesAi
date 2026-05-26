"use client";

/** Markdown 分栏编辑（技能/提示词等，链路 §9）。 */
import { useState } from "react";
import { CodeEditor } from "@/components/editor/CodeEditor";
import { MarkdownPreview } from "@/components/editor/MarkdownPreview";

export type MarkdownViewMode = "edit" | "preview" | "split";

type Props = {
  value: string;
  onChange: (value: string) => void;
  /** 编辑区 aria-label */
  ariaLabel?: string;
  defaultViewMode?: MarkdownViewMode;
  fill?: boolean;
  className?: string;
};

function ViewModeTabs({
  mode,
  onChange,
}: {
  mode: MarkdownViewMode;
  onChange: (mode: MarkdownViewMode) => void;
}) {
  const tabs: { key: MarkdownViewMode; label: string }[] = [
    { key: "edit", label: "编辑" },
    { key: "split", label: "分栏" },
    { key: "preview", label: "预览" },
  ];
  return (
    <div
      className="inline-flex rounded-lg border border-line bg-surface-muted/50 p-0.5"
      role="tablist"
      aria-label="Markdown 视图"
    >
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          role="tab"
          aria-selected={mode === tab.key}
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

export function MarkdownSplitEditor({
  value,
  onChange,
  ariaLabel = "Markdown 正文",
  defaultViewMode = "split",
  fill = false,
  className = "",
}: Props) {
  const [viewMode, setViewMode] = useState<MarkdownViewMode>(defaultViewMode);
  const showEdit = viewMode === "edit" || viewMode === "split";
  const showPreview = viewMode === "preview" || viewMode === "split";

  return (
    <div
      className={`flex flex-col gap-2 ${fill ? "min-h-0 flex-1" : ""} ${className}`.trim()}
    >
      <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
        <ViewModeTabs mode={viewMode} onChange={setViewMode} />
      </div>

      <div
        className={`flex gap-3 ${
          fill ? "min-h-0 flex-1" : "min-h-[320px]"
        } ${viewMode === "split" ? "flex-col lg:flex-row" : "flex-col"}`}
      >
        {showEdit && (
          <div
            className={`flex min-w-0 flex-col ${
              viewMode === "split"
                ? "min-h-[200px] flex-1 lg:min-h-0"
                : fill
                  ? "min-h-0 flex-1"
                  : "h-[320px]"
            }`}
          >
            <CodeEditor
              fill={fill || viewMode === "split"}
              language="markdown"
              value={value}
              onChange={onChange}
              aria-label={ariaLabel}
            />
          </div>
        )}

        {showPreview && (
          <section
            className={`flex min-w-0 flex-col overflow-hidden rounded-lg border border-line bg-surface ${
              viewMode === "split"
                ? "min-h-[200px] flex-1 lg:min-h-0"
                : fill
                  ? "min-h-0 flex-1"
                  : "min-h-[200px]"
            }`}
          >
            <header className="shrink-0 border-b border-line-soft px-4 py-2 text-xs font-medium text-ink-muted">
              预览
            </header>
            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
              <MarkdownPreview
                content={value}
                emptyHint="暂无内容，在编辑区输入 Markdown。"
              />
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
