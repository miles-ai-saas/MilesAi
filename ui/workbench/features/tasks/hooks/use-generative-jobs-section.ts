"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { usePagedList } from "@/hooks/use-paged-list";
import { useGenerativeJobMeta } from "@/hooks/use-generative-job-meta";
import { filterBySearch } from "@/lib/filter-search";
import { canCancelGenerativeJob, generativeJobKindFilterOptions } from "@/lib/generative-job-labels";

export type GenerativeJobsListApi = {
  reload: () => void;
  loading: boolean;
};

type HookProps = {
  enabled: boolean;
  search: string;
  filter: string;
  onMsg: (msg: string) => void;
  onExposeList?: (api: GenerativeJobsListApi) => void;
};

export function useGenerativeJobsSection({ enabled, search, filter, onMsg, onExposeList }: HookProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const jobMeta = useGenerativeJobMeta(enabled);
  const [detailJobId, setDetailJobId] = useState<string | null>(null);
  const [selectedJobIds, setSelectedJobIds] = useState<Set<string>>(new Set());

  const jobFromUrl = searchParams.get("job");
  const kindFilter = searchParams.get("gen_kind") || "";

  useEffect(() => {
    if (jobFromUrl && enabled) setDetailJobId(jobFromUrl);
  }, [jobFromUrl, enabled]);

  const setKindFilter = useCallback(
    (kind: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("category", "generative");
      if (kind) params.set("gen_kind", kind);
      else params.delete("gen_kind");
      router.replace(`/workbench/tasks?${params.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

  const closeDetail = useCallback(() => {
    setDetailJobId(null);
    const params = new URLSearchParams(searchParams.toString());
    params.delete("job");
    router.replace(`/workbench/tasks?${params.toString()}`, { scroll: false });
  }, [router, searchParams]);

  const openDetail = useCallback(
    (id: string) => {
      setDetailJobId(id);
      const params = new URLSearchParams(searchParams.toString());
      params.set("category", "generative");
      params.set("job", id);
      router.replace(`/workbench/tasks?${params.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

  const list = usePagedList(
    useCallback(
      (p, s) =>
        api.listGenerativeJobs(p, s, {
          status: filter || undefined,
          kind: kindFilter || undefined,
        }),
      [filter, kindFilter],
    ),
    { enabled, resetKey: `${filter}-${kindFilter}` },
  );

  useEffect(() => {
    if (!enabled) return;
    onExposeList?.({
      reload: () => void list.reload(),
      loading: list.loading,
    });
  }, [enabled, list.reload, list.loading, onExposeList]);

  const filtered = useMemo(
    () =>
      filterBySearch(list.items, search, (j) => {
        const p = j.params?.prompt;
        return `${j.id} ${j.source} ${j.kind} ${j.progress_message ?? ""} ${j.error_message ?? ""} ${typeof p === "string" ? p : ""}`;
      }),
    [list.items, search],
  );

  const pageStats = useMemo(() => {
    let running = 0;
    let pending = 0;
    let failed = 0;
    for (const j of list.items) {
      if (j.status === "running") running += 1;
      else if (j.status === "pending") pending += 1;
      else if (j.status === "failed") failed += 1;
    }
    return { running, pending, failed };
  }, [list.items]);

  const onCancel = async (id: string) => {
    onMsg("");
    try {
      await api.cancelGenerativeJob(id);
      onMsg("已取消");
      await list.reload();
    } catch (e) {
      onMsg(e instanceof Error ? e.message : "取消失败");
    }
  };

  const onRetry = async (id: string) => {
    onMsg("");
    try {
      await api.retryGenerativeJob(id);
      onMsg("已重新提交");
      await list.reload();
    } catch (e) {
      onMsg(e instanceof Error ? e.message : "重试失败");
    }
  };

  const cancellableOnPage = useMemo(() => filtered.filter((j) => canCancelGenerativeJob(j.status)), [filtered]);

  const toggleJobSelection = (jobId: string, checked: boolean) => {
    setSelectedJobIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(jobId);
      else next.delete(jobId);
      return next;
    });
  };

  const batchCancelSelected = async () => {
    if (selectedJobIds.size === 0) return;
    onMsg("");
    try {
      const res = await api.batchCancelGenerativeJobs([...selectedJobIds]);
      onMsg(`已取消 ${res.cancelled.length} 条${res.skipped.length ? `，跳过 ${res.skipped.length} 条` : ""}`);
      setSelectedJobIds(new Set());
      await list.reload();
    } catch (e) {
      onMsg(e instanceof Error ? e.message : "批量取消失败");
    }
  };

  const kindFilterOptions = generativeJobKindFilterOptions();

  return {
    jobMeta,
    detailJobId,
    selectedJobIds,
    kindFilter,
    setKindFilter,
    closeDetail,
    openDetail,
    list,
    filtered,
    pageStats,
    cancellableOnPage,
    kindFilterOptions,
    onCancel,
    onRetry,
    toggleJobSelection,
    batchCancelSelected,
  };
}

export type GenerativeJobsSectionVm = ReturnType<typeof useGenerativeJobsSection>;
