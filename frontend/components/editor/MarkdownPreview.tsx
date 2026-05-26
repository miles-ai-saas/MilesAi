"use client";

/** Markdown 预览（链路 §9）。 */
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Props = {
  content: string;
  className?: string;
  emptyHint?: string;
};

export function MarkdownPreview({
  content,
  className = "",
  emptyHint = "暂无正文，在左侧编辑 Markdown。",
}: Props) {
  const trimmed = content.trim();
  if (!trimmed) {
    return <p className="text-sm text-ink-faint">{emptyHint}</p>;
  }

  return (
    <article className={`markdown-preview ${className}`.trim()}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </article>
  );
}
