"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
import type { BizOpportunity } from "@/lib/types";
import { OPPORTUNITY_STAGES, stageBadgeClass } from "@/features/opportunities/lib/opportunity-labels";
import type { OpportunitiesPageVm } from "@/features/opportunities/hooks/use-opportunities-page";

export function OpportunitiesPipelineBoard({ vm }: { vm: OpportunitiesPageVm }) {
  const { pipeline, pipelineLoading, onStageChange, onConvert, onDelete, openDetail } = vm;
  const { canWriteOpportunity } = useBizPermissions();

  const grouped = useMemo(() => {
    const map: Record<string, BizOpportunity[]> = {};
    for (const stage of OPPORTUNITY_STAGES) map[stage.key] = [];
    for (const opp of pipeline) {
      (map[opp.stage] ??= []).push(opp);
    }
    return map;
  }, [pipeline]);

  if (pipelineLoading) return <p className="text-sm text-ink-muted">加载看板…</p>;

  return (
    <div className="flex gap-3 overflow-x-auto pb-2">
      {OPPORTUNITY_STAGES.map((stage) => (
        <div
          key={stage.key}
          className="min-w-[14rem] flex-1 rounded-lg border border-line bg-surface-muted/40"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            if (!canWriteOpportunity) return;
            const id = e.dataTransfer.getData("text/opportunity-id");
            if (id) void onStageChange(id, stage.key);
          }}
        >
          <div className="flex items-center justify-between border-b border-line px-3 py-2">
            <span className="text-xs font-semibold text-ink">{stage.label}</span>
            <span className="text-xs text-ink-faint">{grouped[stage.key]?.length ?? 0}</span>
          </div>
          <div className="space-y-2 p-2">
            {(grouped[stage.key] ?? []).length === 0 && (
              <p className="px-1 py-4 text-center text-xs text-ink-faint">暂无</p>
            )}
            {(grouped[stage.key] ?? []).map((opp) => (
              <div
                key={opp.id}
                draggable={canWriteOpportunity}
                onDragStart={(e) => {
                  if (!canWriteOpportunity) {
                    e.preventDefault();
                    return;
                  }
                  e.dataTransfer.setData("text/opportunity-id", opp.id);
                }}
                className={`card p-3 ${canWriteOpportunity ? "cursor-grab active:cursor-grabbing" : ""}`}
              >
                <button
                  type="button"
                  onClick={() => openDetail(opp.id)}
                  className="font-medium text-sm text-ink hover:text-brand text-left"
                >
                  {opp.name}
                </button>
                <p className="mt-1 text-xs text-ink-muted">
                  {opp.expected_value != null ? `¥${opp.expected_value.toLocaleString()}` : "—"}
                  {opp.probability != null ? ` · ${opp.probability}%` : ""}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span className={`rounded px-1.5 py-0.5 text-[10px] ${stageBadgeClass(opp.stage)}`}>
                    {stage.label}
                  </span>
                  {canWriteOpportunity && opp.stage === "won" && !opp.converted_to_project_id ? (
                    <button type="button" className="text-[10px] text-brand hover:underline" onClick={() => void onConvert(opp)}>
                      转项目
                    </button>
                  ) : null}
                  {opp.converted_to_project_id ? (
                    <Link href={`/business/projects/${opp.converted_to_project_id}`} className="text-[10px] text-brand hover:underline">
                      查看项目
                    </Link>
                  ) : null}
                  {canWriteOpportunity && (
                    <button type="button" className="text-[10px] text-red-600 hover:underline" onClick={() => onDelete(opp)}>
                      删除
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
