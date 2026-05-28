"use client";

import Link from "next/link";
import type { AppInstallResult } from "@/lib/types";

export const MARKETPLACE_PAGE_DESC = "浏览并安装已审核上架的应用；可将本租户知识库、流程或智能体打包为应用，审核通过后供其他租户安装。";

export function MarketplaceStatChip({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface px-4 py-3 shadow-card">
      <p className="text-xs text-ink-muted">{label}</p>
      <p className="mt-0.5 text-2xl font-bold tabular-nums text-brand">{value}</p>
      {hint ? <p className="mt-1 text-xs text-ink-faint">{hint}</p> : null}
    </div>
  );
}

export function MarketplacePageMessage({ message, onDismiss }: { message: string; onDismiss?: () => void }) {
  return (
    <div className="col-span-full flex items-start justify-between gap-3 rounded-xl border border-line bg-brand-light/40 px-4 py-3 text-sm text-ink">
      <p className="min-w-0 flex-1">{message}</p>
      {onDismiss ? (
        <button type="button" className="shrink-0 text-xs text-ink-muted hover:text-ink" onClick={onDismiss}>
          关闭
        </button>
      ) : null}
    </div>
  );
}

export function MarketplaceInstallSuccessBanner({ result, onDismiss }: { result: AppInstallResult; onDismiss: () => void }) {
  return (
    <div className="col-span-full rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
      <div className="flex items-start justify-between gap-3">
        <p className="font-medium">{result.message || "安装完成"}</p>
        <button type="button" className="text-xs opacity-70 hover:opacity-100" onClick={onDismiss}>
          关闭
        </button>
      </div>
      <ul className="mt-2 space-y-1 text-xs">
        {result.kb_id ? (
          <li>
            知识库 →{" "}
            <Link href={`/workbench/kb/${result.kb_id}`} className="underline">
              管理文档
            </Link>
          </li>
        ) : null}
        {result.flow_id ? (
          <li>
            流程 →{" "}
            <Link href={`/workbench/flows/${result.flow_id}/edit`} className="underline">
              编辑画布
            </Link>
          </li>
        ) : null}
        {result.agent_id ? (
          <li>
            智能体 →{" "}
            <Link href="/workbench/agents/chat" className="underline">
              去对话
            </Link>
          </li>
        ) : null}
      </ul>
    </div>
  );
}
