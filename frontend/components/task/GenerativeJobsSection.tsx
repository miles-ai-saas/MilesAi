"use client";

/** 任务中心 — 生成任务（generative_jobs）列表区块。 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { usePagedList } from "@/hooks/use-paged-list";
import { useGenerativeJobMeta } from "@/hooks/use-generative-job-meta";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { GenerativeJobDetailDialog } from "@/components/task/GenerativeJobDetailDialog";
import { filterBySearch } from "@/lib/filter-search";
import {
  canCancelGenerativeJob,
  canRetryGenerativeJob,
  generativeJobKindFilterOptions,
  generativeJobKindLabel,
  generativeJobSourceLabel,
  generativeJobStatusBadgeClass,
  generativeJobStatusLabel,
} from "@/lib/generative-job-labels";
import type { GenerativeJobsMeta } from "@/lib/generative-job-labels";
import type { GenerativeJobOut } from "@/lib/types";

function StatChip({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface px-4 py-3 shadow-card">
      <p className="text-xs text-ink-muted">{label}</p>
      <p className="mt-0.5 text-2xl font-bold tabular-nums text-brand">{value}</p>
      {hint ? <p className="mt-1 text-xs text-ink-faint">{hint}</p> : null}
    </div>
  );
}

function GenerativeJobRow({
  job,
  jobMeta,
  onViewDetail,
  onCancel,
  onRetry,
}: {
  job: GenerativeJobOut;
  jobMeta: GenerativeJobsMeta | null;
  onViewDetail: () => void;
  onCancel: () => void;
  onRetry: () => void;
}) {
  const prompt =
    job.params && typeof job.params.prompt === "string"
      ? job.params.prompt
      : "";
  return (
    <article className="rounded-xl border border-line bg-surface p-4 shadow-card transition hover:border-brand/20">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium text-ink">{generativeJobKindLabel(job.kind)}</h3>
            <span
              className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${generativeJobStatusBadgeClass(job.status)}`}
            >
              {generativeJobStatusLabel(job.status, jobMeta)}
            </span>
            {job.progress_percent != null &&
            (job.status === "pending" || job.status === "running") ? (
              <span className="text-xs text-ink-muted">{job.progress_percent}%</span>
            ) : null}
          </div>
          <p className="mt-1 text-xs text-ink-muted">
            {generativeJobSourceLabel(job.source, jobMeta)} · {job.id.slice(0, 8)}…
          </p>
          {prompt ? (
            <p className="mt-2 line-clamp-2 text-sm text-ink-muted">{prompt}</p>
          ) : null}
          {job.progress_message &&
          (job.status === "pending" || job.status === "running") ? (
            <p className="mt-1 text-xs text-amber-800">{job.progress_message}</p>
          ) : null}
          <time className="mt-2 block text-xs text-ink-faint">
            {new Date(job.created_at).toLocaleString("zh-CN")}
          </time>
          {job.error_message ? (
            <p className="mt-2 rounded-lg bg-red-50/80 px-3 py-2 text-xs text-red-700 line-clamp-2">
              {job.error_message}
            </p>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-wrap gap-3">
          <button type="button" className="btn-secondary px-3 py-1.5 text-xs" onClick={onViewDetail}>
            查看详情
          </button>
          {canCancelGenerativeJob(job.status) && (
            <button type="button" className="text-xs text-red-600 hover:underline" onClick={onCancel}>
              取消
            </button>
          )}
          {canRetryGenerativeJob(job.status) && (
            <button type="button" className="text-xs text-brand hover:underline" onClick={onRetry}>
              重试
            </button>
          )}
        </div>
      </div>
      {!canCancelGenerativeJob(job.status) &&
      job.progress_percent != null &&
      job.progress_percent > 0 &&
      job.progress_percent < 100 ? (
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-surface-muted">
          <div
            className="h-full rounded-full bg-brand transition-all"
            style={{ width: `${job.progress_percent}%` }}
          />
        </div>
      ) : null}
    </article>
  );
}

export type GenerativeJobsListApi = {
  reload: () => void;
  loading: boolean;
};

type Props = {
  enabled: boolean;
  search: string;
  filter: string;
  msg: string;
  onMsg: (msg: string) => void;
  /** 供任务中心页头「刷新」按钮调用 */
  onExposeList?: (api: GenerativeJobsListApi) => void;
};

export function GenerativeJobsSection({
  enabled,
  search,
  filter,
  msg,
  onMsg,
  onExposeList,
}: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const jobMeta = useGenerativeJobMeta(enabled);
  const [detailJobId, setDetailJobId] = useState<string | null>(null);

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

  if (!enabled) return null;

  if (list.loading && list.items.length === 0) {
    return <p className="col-span-full py-16 text-center text-sm text-ink-muted">加载中…</p>;
  }

  return (
    <>
      <div className="col-span-full flex flex-wrap gap-2">
        {generativeJobKindFilterOptions().map((opt) => (
          <button
            key={opt.value || "all"}
            type="button"
            onClick={() => setKindFilter(opt.value)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              kindFilter === opt.value
                ? "bg-brand text-white"
                : "bg-surface text-ink-muted ring-1 ring-line hover:text-ink"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <div className="col-span-full grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <StatChip label="生成任务总数" value={String(list.total)} hint="当前筛选" />
        <StatChip
          label="本页进行中"
          value={String(pageStats.running + pageStats.pending)}
          hint={`失败 ${pageStats.failed}（当前页）`}
        />
        <StatChip label="本页展示" value={String(filtered.length)} hint="受搜索影响" />
      </div>

      <div className="col-span-full space-y-3">
        {!list.loading && filtered.length === 0 && (
          <p className="rounded-xl border border-dashed border-line py-12 text-center text-sm text-ink-faint">
            暂无生成任务。在智能体对话或流程中生图/生视频后会出现在此。
          </p>
        )}
        {filtered.map((j) => (
          <GenerativeJobRow
            key={j.id}
            job={j}
            jobMeta={jobMeta}
            onViewDetail={() => openDetail(j.id)}
            onCancel={() => void onCancel(j.id)}
            onRetry={() => void onRetry(j.id)}
          />
        ))}
      </div>

      {!list.loading ? (
        <div className="col-span-full">
          <ResourceListFooter
            page={list.page}
            size={list.size}
            total={list.total}
            onPageChange={list.setPage}
          />
        </div>
      ) : null}

      <GenerativeJobDetailDialog
        open={!!detailJobId}
        jobId={detailJobId}
        jobMeta={jobMeta}
        onClose={closeDetail}
        onChanged={() => void list.reload()}
      />
    </>
  );
}
