"use client";

import Link from "next/link";
import { OpportunitiesPipelineBoard } from "@/features/opportunities/components/OpportunitiesPipelineBoard";
import { OpportunitiesTable } from "@/features/opportunities/components/OpportunitiesTable";
import type { OpportunitiesPageVm } from "@/features/opportunities/hooks/use-opportunities-page";

export function OpportunitiesPageView({ vm }: { vm: OpportunitiesPageVm }) {
  const { ready, viewMode, setViewMode, confirmDialog } = vm;
  if (!ready) return <p className="text-sm text-ink-muted">加载中…</p>;

  return (
    <div className="w-full">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink">商机</h1>
          <p className="mt-1 text-sm text-ink-muted">拖拽卡片推进阶段，赢单后可一键转为项目</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-line p-0.5 text-xs">
            <button type="button" className={`rounded-md px-3 py-1.5 ${viewMode === "board" ? "bg-brand-light text-brand" : "text-ink-muted"}`} onClick={() => setViewMode("board")}>看板</button>
            <button type="button" className={`rounded-md px-3 py-1.5 ${viewMode === "table" ? "bg-brand-light text-brand" : "text-ink-muted"}`} onClick={() => setViewMode("table")}>列表</button>
          </div>
          <Link href="/business/opportunities/new" className="btn-primary text-sm">新建商机</Link>
        </div>
      </div>
      {viewMode === "board" ? <OpportunitiesPipelineBoard vm={vm} /> : <OpportunitiesTable vm={vm} />}
      {confirmDialog}
    </div>
  );
}
