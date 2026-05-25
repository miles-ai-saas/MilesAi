"use client";

import { useEffect, useRef, useState } from "react";
import { formatToolUpdatedAt, toolSourceLabel } from "@/lib/tool-labels";
import type { ToolCatalogItem } from "@/lib/types";

type Props = {
  tool: ToolCatalogItem;
  onTest: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
};

export function ToolCard({ tool, onTest, onEdit, onDelete }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const readonly = tool.source !== "custom";

  useEffect(() => {
    if (!menuOpen) return;
    const close = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [menuOpen]);

  return (
    <article className="resource-card relative !min-h-[176px]">
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-light text-lg">
          🔧
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h3 className="font-medium text-ink line-clamp-1">{tool.name}</h3>
              <p className="text-[10px] text-ink-faint">{tool.slug}</p>
            </div>
            <div className="relative shrink-0" ref={menuRef}>
              <button
                type="button"
                aria-label="更多操作"
                className="rounded px-1.5 py-0.5 text-ink-muted hover:bg-surface-muted"
                onClick={() => setMenuOpen((v) => !v)}
              >
                ···
              </button>
              {menuOpen && (
                <div className="absolute right-0 z-10 mt-1 min-w-[8rem] rounded-lg border border-line bg-surface py-1 shadow-panel">
                  <button
                    type="button"
                    className="block w-full px-3 py-1.5 text-left text-xs hover:bg-surface-muted"
                    onClick={() => {
                      setMenuOpen(false);
                      onTest();
                    }}
                  >
                    试调用
                  </button>
                  {!readonly && onEdit && (
                    <button
                      type="button"
                      className="block w-full px-3 py-1.5 text-left text-xs hover:bg-surface-muted"
                      onClick={() => {
                        setMenuOpen(false);
                        onEdit();
                      }}
                    >
                      编辑
                    </button>
                  )}
                  {!readonly && onDelete && (
                    <button
                      type="button"
                      className="block w-full px-3 py-1.5 text-left text-xs text-red-600 hover:bg-red-50"
                      onClick={() => {
                        setMenuOpen(false);
                        onDelete();
                      }}
                    >
                      删除
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
          <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-ink-muted">
            {tool.description || "—"}
          </p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <span className="rounded border border-brand/20 bg-brand-light/30 px-2 py-0.5 text-[10px] font-medium text-brand">
          {toolSourceLabel(tool.source)}
        </span>
        {tool.category_name && (
          <span className="rounded border border-line bg-surface-muted px-2 py-0.5 text-[10px] text-ink-muted">
            {tool.category_name}
          </span>
        )}
        {tool.version && (
          <span className="rounded border border-line bg-surface-muted px-2 py-0.5 text-[10px] text-ink-muted">
            v{tool.version}
          </span>
        )}
      </div>

      {tool.mcp_service_name && (
        <p className="mt-2 text-xs text-ink-faint">来自 {tool.mcp_service_name}</p>
      )}

      <p className="mt-auto pt-3 text-xs text-ink-faint">
        {formatToolUpdatedAt(tool) ? `更新于 ${formatToolUpdatedAt(tool)}` : ""}
      </p>
    </article>
  );
}
