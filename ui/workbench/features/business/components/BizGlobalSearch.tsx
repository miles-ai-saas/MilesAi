"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { BizSearchHit } from "@/lib/types";

const KIND_LABELS: Record<BizSearchHit["kind"], string> = {
  client: "客户",
  project: "项目",
  opportunity: "商机",
  contract: "合同",
};

function hitHref(hit: BizSearchHit): string {
  switch (hit.kind) {
    case "client":
      return `/business/clients/detail?id=${hit.id}`;
    case "project":
      return `/business/projects/detail?id=${hit.id}`;
    case "opportunity":
      return `/business/opportunities/detail?id=${hit.id}`;
    case "contract":
      return `/business/contracts/detail?id=${hit.id}`;
  }
}

export function BizGlobalSearch() {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<BizSearchHit[]>([]);
  const [loading, setLoading] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  const runSearch = useCallback(async (q: string) => {
    const trimmed = q.trim();
    if (trimmed.length < 1) {
      setItems([]);
      return;
    }
    setLoading(true);
    try {
      const res = await api.searchBiz(trimmed);
      setItems(res.items);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    const t = window.setTimeout(() => void runSearch(query), 250);
    return () => window.clearTimeout(t);
  }, [query, open, runSearch]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  return (
    <div ref={wrapRef} className="relative hidden md:block">
      <input
        type="search"
        placeholder="搜索客户、项目、商机…"
        className="input-field h-8 w-52 text-sm lg:w-64"
        value={query}
        onFocus={() => setOpen(true)}
        onChange={(e) => setQuery(e.target.value)}
      />
      {open && (query.trim() || items.length > 0) && (
        <div className="absolute right-0 top-full z-50 mt-1 w-80 rounded-lg border border-line bg-surface shadow-panel">
          {loading ? (
            <p className="p-3 text-xs text-ink-muted">搜索中…</p>
          ) : items.length === 0 ? (
            <p className="p-3 text-xs text-ink-faint">{query.trim() ? "无匹配结果" : "输入关键词搜索"}</p>
          ) : (
            <ul className="max-h-72 overflow-y-auto py-1">
              {items.map((hit) => (
                <li key={`${hit.kind}-${hit.id}`}>
                  <Link
                    href={hitHref(hit)}
                    className="block px-3 py-2 hover:bg-surface-muted"
                    onClick={() => setOpen(false)}
                  >
                    <p className="text-sm font-medium text-ink">{hit.title}</p>
                    <p className="text-xs text-ink-muted">
                      {KIND_LABELS[hit.kind]}
                      {hit.subtitle ? ` · ${hit.subtitle}` : ""}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
