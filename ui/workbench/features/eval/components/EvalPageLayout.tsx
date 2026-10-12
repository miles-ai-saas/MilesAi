"use client";

import type { ReactNode } from "react";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import type { EvalPageVm, EvalTab } from "@/features/eval/hooks/use-eval-page";

const EVAL_PAGE_DESC =
  "管理评测数据集与用例，创建运行并查看智能体批量评测结果（规则 / 自动打分）。";

const EVAL_TABS: { key: EvalTab; label: string }[] = [
  { key: "datasets", label: "数据集" },
  { key: "runs", label: "运行" },
  { key: "run_detail", label: "运行详情" },
];

type Props = {
  vm: EvalPageVm;
  headerAction?: ReactNode;
  children: ReactNode;
};

export function EvalPageLayout({ vm, headerAction, children }: Props) {
  const search = vm.tab === "datasets" ? vm.datasetSearch : vm.tab === "runs" ? vm.runSearch : "";
  const onSearchChange =
    vm.tab === "datasets" ? vm.setDatasetSearch : vm.tab === "runs" ? vm.setRunSearch : () => {};
  const showSearch = vm.tab === "datasets" || vm.tab === "runs";
  const loading =
    vm.tab === "datasets" ? vm.datasetsList.loading : vm.tab === "runs" ? vm.runsList.loading : vm.runDetailLoading;

  const defaultHeader = (
    <button
      type="button"
      onClick={() => {
        if (vm.tab === "datasets") vm.reloadDatasets();
        else if (vm.tab === "runs") vm.reloadRuns();
        else vm.reloadRunDetail();
      }}
      className="btn-ghost text-sm"
      disabled={loading}
    >
      {loading ? "刷新中…" : "刷新"}
    </button>
  );

  return (
    <ResourceListLayout
      title="评测"
      description={EVAL_PAGE_DESC}
      tabs={EVAL_TABS}
      activeTab={vm.tab}
      onTabChange={vm.onTabChange}
      search={search}
      onSearchChange={onSearchChange}
      searchPlaceholder={vm.tab === "datasets" ? "搜索数据集" : "搜索运行"}
      showSearch={showSearch}
      loading={loading}
      headerAction={headerAction ?? defaultHeader}
    >
      {children}
    </ResourceListLayout>
  );
}
