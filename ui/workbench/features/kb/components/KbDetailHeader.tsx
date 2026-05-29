"use client";

import Link from "next/link";
import { KbMetaChips } from "@/features/kb/components/KbMetaChips";
import { KbQuotaBar } from "@/features/kb/components/KbQuotaBar";
import type { KbDetailPageVm } from "@/features/kb/hooks/use-kb-detail-page";

export function KbDetailHeader({ vm }: { vm: KbDetailPageVm }) {
  const kb = vm.kb!;
  return (
    <>
      <nav className="flex items-center gap-2 text-sm text-ink-muted">
        <Link href="/workbench/kb" className="text-brand hover:underline">
          知识库
        </Link>
        <span aria-hidden>/</span>
        <span className="truncate font-medium text-ink">{kb.name}</span>
      </nav>

      <header className="rounded-xl border border-line bg-surface p-5 shadow-card">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <h1 className="text-xl font-bold tracking-tight text-ink">{kb.name}</h1>
            <p className="mt-1 text-sm text-ink-muted">{kb.description || "暂无描述"}</p>
            <KbMetaChips kb={kb} />
            <KbQuotaBar quota={vm.quota} loading={vm.quotaLoading} variant="detail" className="mt-2" />
          </div>
          <div className="flex shrink-0 gap-2">
            <button type="button" className="btn-ghost text-sm" onClick={vm.openSettings}>
              设置
            </button>
            <button type="button" className="btn-ghost text-sm text-red-600 hover:bg-red-50" onClick={vm.onDeleteKb}>
              删除
            </button>
          </div>
        </div>
        {vm.hasProcessing ? (
          <p className="mt-4 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-900">
            有文档正在后台入库，请点击文档列表旁的刷新按钮查看最新状态。
          </p>
        ) : null}
      </header>
    </>
  );
}
