"use client";

import type { ReactNode } from "react";

export type ResourceTab = { key: string; label: string };

type Props = {
  title: string;
  description: string;
  searchPlaceholder?: string;
  search: string;
  onSearchChange: (value: string) => void;
  tabs?: ResourceTab[];
  activeTab?: string;
  onTabChange?: (key: string) => void;
  loading?: boolean;
  headerAction?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
  showSearch?: boolean;
};

export function ResourceListLayout({
  title,
  description,
  searchPlaceholder = "搜索名称",
  search,
  onSearchChange,
  tabs,
  activeTab = "",
  onTabChange,
  loading,
  headerAction,
  footer,
  children,
  showSearch = true,
}: Props) {
  return (
    <div className="resource-page-shell">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-ink">{title}</h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-ink-muted">{description}</p>
      </div>

      <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-6 border-b border-line sm:border-0">
          {(tabs ?? [{ key: "", label: "全部" }]).map((tab) => {
            const active = (tabs ? activeTab : "") === tab.key;
            return (
              <button
                key={tab.key || "all"}
                type="button"
                onClick={() => onTabChange?.(tab.key)}
                className={`border-b-2 pb-2 text-sm transition ${
                  active
                    ? "border-brand font-medium text-brand"
                    : "border-transparent text-ink-muted hover:text-ink"
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-4">
          {headerAction}
          {showSearch && (
            <label className="relative block w-full sm:w-72">
              <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint">
                <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
                  <path
                    fillRule="evenodd"
                    d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z"
                    clipRule="evenodd"
                  />
                </svg>
              </span>
              <input
                type="search"
                value={search}
                onChange={(e) => onSearchChange(e.target.value)}
                placeholder={searchPlaceholder}
                className="input-field w-full py-2 pl-9 pr-3"
              />
            </label>
          )}
        </div>
      </div>

      {loading ? (
        <p className="py-16 text-center text-sm text-ink-muted">加载中…</p>
      ) : (
        <>
          <div className="resource-card-grid">{children}</div>
          {footer && <div className="mt-6">{footer}</div>}
        </>
      )}
    </div>
  );
}
