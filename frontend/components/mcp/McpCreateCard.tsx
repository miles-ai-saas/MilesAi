"use client";

/** 列表页左侧「添加 MCP」卡片：按 HTTP / SSE / STDIO 分入口打开创建弹窗。 */

import type { McpTransportTab } from "@/lib/mcp-labels";

const ENTRIES: {
  transport: Exclude<McpTransportTab, "">;
  label: string;
  hint: string;
}[] = [
  { transport: "http", label: "HTTP", hint: "基于 HTTP/HTTPS 协议的 MCP 服务器" },
  { transport: "sse", label: "SSE", hint: "基于 Server-Sent Events 的 MCP 服务器" },
  { transport: "stdio", label: "STDIO", hint: "基于标准输入输出的 MCP 服务器" },
];

type Props = {
  onAdd: (transport: Exclude<McpTransportTab, "">) => void;
};

export function McpCreateCard({ onAdd }: Props) {
  return (
    <article className="resource-add-card !items-stretch !justify-start !p-4">
      <p className="text-sm font-medium text-ink">添加 MCP 服务</p>
      <ul className="mt-3 flex flex-1 flex-col gap-2">
        {ENTRIES.map((e) => (
          <li key={e.transport}>
            <button
              type="button"
              onClick={() => onAdd(e.transport)}
              className="flex w-full items-start gap-3 rounded-lg border border-line-soft bg-surface px-3 py-2.5 text-left transition hover:border-brand/30 hover:bg-brand-light/20"
            >
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-brand-light text-sm font-semibold text-brand">
                +
              </span>
              <span>
                <span className="block text-sm font-medium text-ink">{e.label}</span>
                <span className="mt-0.5 block text-xs leading-snug text-ink-muted">{e.hint}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </article>
  );
}
