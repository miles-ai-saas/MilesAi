"use client";

import { useEffect, useRef } from "react";
import { agentModeLabel } from "@/lib/agent-utils";
import type { Agent } from "@/lib/types";

function agentInitial(name: string) {
  return (name.trim()[0] ?? "?").toUpperCase();
}

export function AgentChatAgentColumn({
  agents,
  total,
  selectedAgentId,
  compact,
  hasMore,
  loadingMore,
  onLoadMore,
  onSelectAgent,
}: {
  agents: Agent[];
  total: number;
  selectedAgentId: string;
  compact: boolean;
  hasMore: boolean;
  loadingMore: boolean;
  onLoadMore: () => void;
  onSelectAgent: (id: string) => void;
}) {
  const scrollRef = useRef<HTMLUListElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = scrollRef.current;
    const sentinel = sentinelRef.current;
    if (!root || !sentinel) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && hasMore && !loadingMore) {
          onLoadMore();
        }
      },
      { root, rootMargin: "64px", threshold: 0 },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, loadingMore, onLoadMore, agents.length]);

  const listContent = agents.map((a) => (
    <li key={a.id}>
      {compact ? (
        <button
          type="button"
          title={`${a.name} · ${agentModeLabel(a)}`}
          onClick={() => onSelectAgent(a.id)}
          className={`flex h-9 w-9 items-center justify-center rounded-lg text-sm font-medium transition ${
            selectedAgentId === a.id ? "bg-brand text-brand-foreground shadow-sm" : "text-ink-muted hover:bg-brand-light hover:text-brand"
          }`}
        >
          {agentInitial(a.name)}
        </button>
      ) : (
        <button
          type="button"
          onClick={() => onSelectAgent(a.id)}
          className={`mb-1 w-full rounded-lg border px-2.5 py-2 text-left text-sm transition ${
            selectedAgentId === a.id ? "border-brand/30 bg-brand-light" : "border-transparent hover:border-line hover:bg-brand-light/40"
          }`}
        >
          <p className="truncate font-medium text-ink">{a.name}</p>
          <p className="mt-0.5 truncate text-xs text-ink-muted">{agentModeLabel(a)}</p>
        </button>
      )}
    </li>
  ));

  const loadTail =
    hasMore || loadingMore ? (
      <li className={compact ? "py-1" : "py-2"}>
        <div ref={sentinelRef} className={`flex items-center justify-center text-[10px] text-ink-faint ${compact ? "min-h-6" : "min-h-8"}`}>
          {loadingMore ? "加载中…" : ""}
        </div>
      </li>
    ) : null;

  if (compact) {
    return (
      <ul ref={scrollRef} className="flex min-h-0 flex-1 flex-col items-center gap-1 overflow-y-auto py-2">
        {listContent}
        {loadTail}
      </ul>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="shrink-0 border-b border-line-soft px-3 py-2.5">
        <p className="text-xs font-medium text-ink">智能体</p>
        <p className="mt-0.5 text-[10px] text-ink-faint">
          共 {total} 个{agents.length < total ? ` · 已加载 ${agents.length}` : ""}
        </p>
      </div>
      <ul ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto p-2">
        {listContent}
        {loadTail}
      </ul>
    </div>
  );
}
