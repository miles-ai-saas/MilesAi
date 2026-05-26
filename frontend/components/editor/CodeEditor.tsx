"use client";

/** 代码/文本编辑器封装（技能文件等，链路 §9）。 */
import { useMemo } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { markdown } from "@codemirror/lang-markdown";
import { python } from "@codemirror/lang-python";
import { EditorView } from "@codemirror/view";

export type CodeEditorLanguage = "python" | "markdown" | "text";

const milesEditorTheme = EditorView.theme(
  {
    "&": {
      fontSize: "13px",
      fontFamily:
        'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
      backgroundColor: "var(--surface)",
      color: "var(--ink)",
    },
    ".cm-content": {
      padding: "10px 0",
      caretColor: "var(--brand)",
    },
    ".cm-cursor, .cm-dropCursor": {
      borderLeftColor: "var(--brand)",
    },
    "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, ::selection": {
      backgroundColor: "var(--brand-light) !important",
    },
    ".cm-gutters": {
      backgroundColor: "var(--surface-muted)",
      color: "var(--ink-muted)",
      borderRight: "1px solid var(--line)",
    },
    ".cm-activeLineGutter": {
      backgroundColor: "var(--brand-light)",
      color: "var(--ink)",
    },
    ".cm-activeLine": {
      backgroundColor: "color-mix(in srgb, var(--brand-light) 55%, transparent)",
    },
  },
  { dark: false },
);

const focusedOutline = EditorView.theme({
  "&.cm-focused": {
    outline: "2px solid color-mix(in srgb, var(--brand) 25%, transparent)",
    outlineOffset: "-1px",
  },
});

function languageExtension(language: CodeEditorLanguage) {
  if (language === "python") return python();
  if (language === "markdown") return markdown();
  return [];
}

export function codeLanguageFromPath(path: string): CodeEditorLanguage {
  const lower = path.toLowerCase();
  if (lower.endsWith(".md") || lower.endsWith(".markdown")) return "markdown";
  if (lower.endsWith(".py")) return "python";
  return "text";
}

type Props = {
  value: string;
  onChange: (value: string) => void;
  language?: CodeEditorLanguage;
  /** 固定高度，如 420px */
  height?: string;
  /** 在 flex 容器内占满剩余高度 */
  fill?: boolean;
  readOnly?: boolean;
  className?: string;
  "aria-label"?: string;
};

export function CodeEditor({
  value,
  onChange,
  language = "text",
  height,
  fill = false,
  readOnly = false,
  className = "",
  "aria-label": ariaLabel,
}: Props) {
  const extensions = useMemo(
    () => [milesEditorTheme, focusedOutline, languageExtension(language), EditorView.lineWrapping],
    [language],
  );

  const shellClass = [
    "overflow-hidden rounded-lg border border-line bg-surface transition-colors",
    "focus-within:border-brand focus-within:ring-2 focus-within:ring-brand/15",
    fill ? "flex min-h-0 flex-1 flex-col" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  const editorHeight = fill ? "100%" : height ?? "320px";

  return (
    <div className={shellClass}>
      <CodeMirror
        value={value}
        height={editorHeight}
        extensions={extensions}
        onChange={onChange}
        readOnly={readOnly}
        basicSetup={{
          lineNumbers: true,
          foldGutter: true,
          highlightActiveLine: true,
          highlightSelectionMatches: true,
          bracketMatching: language === "python",
          indentOnInput: language === "python",
          tabSize: language === "python" ? 4 : 2,
        }}
        aria-label={ariaLabel}
        className={
          fill
            ? "min-h-0 flex-1 [&_.cm-editor]:flex [&_.cm-editor]:h-full [&_.cm-editor]:min-h-0 [&_.cm-editor]:flex-col [&_.cm-scroller]:min-h-0 [&_.cm-scroller]:flex-1"
            : "[&_.cm-editor]:rounded-lg"
        }
      />
    </div>
  );
}
