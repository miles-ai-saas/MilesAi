"use client";

import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import type { EvalPageVm } from "@/features/eval/hooks/use-eval-page";

export function EvalDatasetsTab({ vm }: { vm: EvalPageVm }) {
  const { datasetsList, filteredDatasets, openCreateDataset, openEditDataset, openCases, onDeleteDataset } = vm;

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <AddResourceCard label="新建数据集" hint="用例集合 · exact / contains" onClick={openCreateDataset} />
        {filteredDatasets.map((d) => (
          <ResourceItemCard
            key={d.id}
            title={d.name}
            description={d.description || "暂无描述"}
            meta={
              <span>
                {d.case_count} 个用例 · {new Date(d.created_at).toLocaleString()}
              </span>
            }
            actions={
              <CardActions
                actions={[{ label: "管理用例", onClick: () => openCases(d), variant: "primary" }]}
                onEdit={() => openEditDataset(d)}
                onDelete={() => onDeleteDataset(d)}
              />
            }
          />
        ))}
      </div>
      {!datasetsList.loading && filteredDatasets.length === 0 ? (
        <p className="py-8 text-center text-sm text-ink-muted">暂无数据集，点击上方卡片创建。</p>
      ) : null}
      {!datasetsList.loading ? (
        <ResourceListFooter
          page={datasetsList.page}
          size={datasetsList.size}
          total={datasetsList.total}
          onPageChange={datasetsList.setPage}
          onSizeChange={datasetsList.setSize}
        />
      ) : null}
    </div>
  );
}
