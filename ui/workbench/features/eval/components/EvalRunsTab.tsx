"use client";

import { CardActions } from "@/components/resource/CardActions";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import type { EvalPageVm } from "@/features/eval/hooks/use-eval-page";
import {
  evalRunStatusLabel,
  evalScoringModeLabel,
  formatRunSummary,
} from "@/features/eval/lib/eval-labels";

export function EvalRunsTab({ vm }: { vm: EvalPageVm }) {
  const { runsList, filteredRuns, openRunDetail, startRun, setRunCreateOpen } = vm;

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button type="button" className="btn-sm-primary" onClick={() => setRunCreateOpen(true)}>
          新建运行
        </button>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filteredRuns.map((r) => (
          <ResourceItemCard
            key={r.id}
            title={`运行 ${r.id.slice(0, 8)}…`}
            description={formatRunSummary(r.summary)}
            badge={evalRunStatusLabel(r.status)}
            meta={
              <div className="space-y-1">
                <div>模式：{evalScoringModeLabel(r.scoring_mode)}</div>
                <div className="truncate">Agent：{r.agent_id}</div>
                <div className="truncate">Dataset：{r.dataset_id}</div>
                <div>{new Date(r.created_at).toLocaleString()}</div>
              </div>
            }
            onClick={() => openRunDetail(r.id)}
            actions={
              <CardActions
                actions={[
                  {
                    label: "查看详情",
                    onClick: () => openRunDetail(r.id),
                    variant: "primary",
                  },
                  ...(r.status === "pending"
                    ? [
                        {
                          label: "启动",
                          onClick: () => void startRun(r),
                          variant: "primary" as const,
                        },
                      ]
                    : []),
                ]}
              />
            }
          />
        ))}
      </div>
      {!runsList.loading && filteredRuns.length === 0 ? (
        <p className="py-8 text-center text-sm text-ink-muted">暂无运行记录，点击「新建运行」开始。</p>
      ) : null}
      {!runsList.loading ? (
        <ResourceListFooter
          page={runsList.page}
          size={runsList.size}
          total={runsList.total}
          onPageChange={runsList.setPage}
          onSizeChange={runsList.setSize}
        />
      ) : null}
    </div>
  );
}
