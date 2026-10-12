"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { filterBySearch } from "@/lib/filter-search";
import { isEvalRunActive } from "@/features/eval/lib/eval-labels";
import type { EvalCase, EvalDataset, EvalRun, EvalRunItem, EvalScoringMode } from "@/lib/types";

export type EvalTab = "datasets" | "runs" | "run_detail";

const POLL_MS = 3000;

export function useEvalPage() {
  const { ready } = useRequireAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const [tab, setTab] = useState<EvalTab>("datasets");
  const [datasetSearch, setDatasetSearch] = useState("");
  const [runSearch, setRunSearch] = useState("");

  const [datasetDialogOpen, setDatasetDialogOpen] = useState(false);
  const [editingDataset, setEditingDataset] = useState<EvalDataset | null>(null);

  const [casesDialogOpen, setCasesDialogOpen] = useState(false);
  const [casesDataset, setCasesDataset] = useState<EvalDataset | null>(null);

  const [runCreateOpen, setRunCreateOpen] = useState(false);

  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [runDetail, setRunDetail] = useState<EvalRun | null>(null);
  const [runItems, setRunItems] = useState<EvalRunItem[]>([]);
  const [runItemsTotal, setRunItemsTotal] = useState(0);
  const [runItemsPage, setRunItemsPage] = useState(1);
  const [runDetailLoading, setRunDetailLoading] = useState(false);
  const [runDetailError, setRunDetailError] = useState("");
  const [actionMsg, setActionMsg] = useState("");

  const runFromUrl = searchParams.get("run");

  useEffect(() => {
    if (runFromUrl && ready) {
      setSelectedRunId(runFromUrl);
      setTab("run_detail");
    }
  }, [runFromUrl, ready]);

  const datasetsList = usePagedList(
    useCallback((p, s) => api.listEvalDatasets(p, s), []),
    { enabled: ready },
  );

  const runsList = usePagedList(
    useCallback((p, s) => api.listEvalRuns(p, s), []),
    { enabled: ready },
  );

  const filteredDatasets = useMemo(
    () => filterBySearch(datasetsList.items, datasetSearch, (d) => `${d.name} ${d.description ?? ""}`),
    [datasetsList.items, datasetSearch],
  );

  const filteredRuns = useMemo(
    () =>
      filterBySearch(
        runsList.items,
        runSearch,
        (r) => `${r.id} ${r.status} ${r.agent_id} ${r.dataset_id} ${r.scoring_mode}`,
      ),
    [runsList.items, runSearch],
  );

  const syncRunUrl = useCallback(
    (runId: string | null) => {
      const params = new URLSearchParams(searchParams.toString());
      if (runId) params.set("run", runId);
      else params.delete("run");
      const q = params.toString();
      router.replace(q ? `/workbench/eval?${q}` : "/workbench/eval", { scroll: false });
    },
    [router, searchParams],
  );

  const onTabChange = useCallback(
    (key: string) => {
      const next = key as EvalTab;
      setTab(next);
      if (next !== "run_detail") {
        // keep selected run in URL only when on detail
      }
    },
    [],
  );

  const openCreateDataset = () => {
    setEditingDataset(null);
    setDatasetDialogOpen(true);
  };

  const openEditDataset = (d: EvalDataset) => {
    setEditingDataset(d);
    setDatasetDialogOpen(true);
  };

  const openCases = (d: EvalDataset) => {
    setCasesDataset(d);
    setCasesDialogOpen(true);
  };

  const onDeleteDataset = (d: EvalDataset) => {
    requestConfirm({
      title: "删除数据集",
      message: (
        <>
          确定删除数据集 <span className="font-medium">{d.name}</span>？其用例将一并删除。
        </>
      ),
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deleteEvalDataset(d.id);
        await datasetsList.reload();
      },
    });
  };

  const loadRunDetail = useCallback(
    async (runId: string, page = runItemsPage) => {
      setRunDetailLoading(true);
      setRunDetailError("");
      try {
        const [run, itemsPage] = await Promise.all([
          api.getEvalRun(runId),
          api.listEvalRunItems(runId, page, 20),
        ]);
        setRunDetail(run);
        setRunItems(itemsPage.items);
        setRunItemsTotal(itemsPage.total);
      } catch (e) {
        setRunDetailError(e instanceof Error ? e.message : "加载失败");
      } finally {
        setRunDetailLoading(false);
      }
    },
    [runItemsPage],
  );

  const openRunDetail = useCallback(
    (runId: string) => {
      setSelectedRunId(runId);
      setRunItemsPage(1);
      setTab("run_detail");
      syncRunUrl(runId);
    },
    [syncRunUrl],
  );

  useEffect(() => {
    if (!ready || !selectedRunId || tab !== "run_detail") return;
    void loadRunDetail(selectedRunId, runItemsPage);
  }, [ready, selectedRunId, tab, runItemsPage, loadRunDetail]);

  const reloadRuns = useCallback(() => {
    void runsList.reload();
  }, [runsList.reload]);

  useEffect(() => {
    if (!ready || !selectedRunId || tab !== "run_detail") return;
    if (!runDetail || !isEvalRunActive(runDetail.status)) return;
    const timer = window.setInterval(() => {
      void loadRunDetail(selectedRunId, runItemsPage);
      reloadRuns();
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [ready, selectedRunId, tab, runDetail?.status, runItemsPage, loadRunDetail, reloadRuns]);

  const reloadRunDetail = useCallback(() => {
    if (selectedRunId) void loadRunDetail(selectedRunId, runItemsPage);
  }, [selectedRunId, runItemsPage, loadRunDetail]);

  const startRun = async (run: EvalRun) => {
    setActionMsg("");
    try {
      await api.startEvalRun(run.id);
      setActionMsg("已启动评测任务");
      await runsList.reload();
      if (selectedRunId === run.id) {
        await loadRunDetail(run.id, runItemsPage);
      }
    } catch (e) {
      setActionMsg(e instanceof Error ? e.message : "启动失败");
    }
  };

  const onCreateRun = async (payload: {
    dataset_id: string;
    agent_id: string;
    scoring_mode: EvalScoringMode;
    judge_model_config_id?: string | null;
  }) => {
    const run = await api.createEvalRun(payload);
    await runsList.reload();
    setRunCreateOpen(false);
    openRunDetail(run.id);
    return run;
  };

  return {
    ready,
    tab,
    onTabChange,
    datasetSearch,
    setDatasetSearch,
    runSearch,
    setRunSearch,
    datasetsList,
    runsList,
    filteredDatasets,
    filteredRuns,
    datasetDialogOpen,
    setDatasetDialogOpen,
    editingDataset,
    casesDialogOpen,
    setCasesDialogOpen,
    casesDataset,
    runCreateOpen,
    setRunCreateOpen,
    selectedRunId,
    runDetail,
    runItems,
    runItemsTotal,
    runItemsPage,
    setRunItemsPage,
    runDetailLoading,
    runDetailError,
    actionMsg,
    setActionMsg,
    confirmDialog,
    openCreateDataset,
    openEditDataset,
    openCases,
    onDeleteDataset,
    openRunDetail,
    startRun,
    onCreateRun,
    reloadDatasets: () => void datasetsList.reload(),
    reloadRuns,
    reloadRunDetail,
  };
}

export type EvalPageVm = ReturnType<typeof useEvalPage>;

export type { EvalCase, EvalDataset, EvalRun, EvalRunItem };
